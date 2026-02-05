import base64
import io
import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go

app = Dash(__name__)
server = app.server  # REQUIRED for Render/Gunicorn

# ===================== LAYOUT =====================
app.layout = html.Div([
    html.H1("MK Dons - CEF Dashboard"),

    dcc.Upload(
        id='upload-data',
        children=html.Div(['Drag and Drop or ', html.A('Select Excel File')]),
        style={
            'width': '60%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px auto'
        },
        multiple=False
    ),

    html.Div(id='file-status'),

    dcc.Dropdown(id='participant-dropdown', placeholder="Select a coach", style={"marginTop": "10px"}),
    dcc.Dropdown(id='block-dropdown', placeholder="Select a block", style={"marginTop": "10px"}),

    html.Div(id='group-grid', style={"marginTop": "25px"}),
    dcc.Graph(id='question-chart'),

    html.Hr(),

    html.Div(id='development-lists', style={"display": "flex", "gap": "40px"}),

    html.Hr(),
    html.H2("Block Comparison"),

    html.Div([
        html.Div([
            dcc.Dropdown(id='compare-block-1', placeholder="Select first block"),
            html.Div(id='compare-grid-1')
        ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top"}),

        html.Div([
            dcc.Dropdown(id='compare-block-2', placeholder="Select second block"),
            html.Div(id='compare-grid-2')
        ], style={"width": "48%", "display": "inline-block", "float": "right", "verticalAlign": "top"})
    ])
])

# ===================== GLOBAL STORAGE =====================
blocks = {}
question_cols = []

GROUP_LABELS = [
    "Understanding Self",
    "Coaching Individuals",
    "Coaching Practice",
    "Skill Acquisition",
    "MK Dons",
    "Psychology/Social Support",
    "Relationships",
    "Athletic Development",
    "Wellbeing/Lifestyle"
]

QUESTION_TEXT = {
    1: "Understands their role (IP/VEO)",
    2: "Engages with club coach CPD",
    3: "Effectively communicates (IP/VEO)",
    4: "Engages with players & parents informally (IP/VEO)",
    5: "Understands the game model",
    6: "Seeks to understand decisions (Q)",
    7: "Is positive and inspiring (IP)",
    8: "Sets realistic goals for players (IP/VEO)",
    9: "Use appropriate interventions (IP/VEO)",
    10: "Understands player differences",
    11: "Understands and applies LTPD",
    12: "Supports coaching with video and data (IP/VEO)",
    13: "Introduces sessions",
    14: "Embeds deliberate practice",
    15: "Creates action plans for players (IP)",
    16: "Debriefs sessions (IP/VEO)",
    17: "Uses club coaching methodology (IP)",
    18: "Adopts Club principles (H-O-P)",
    19: "Adopts multi-disc approach",
    20: "Aware of safeguarding policies/procedures",
    21: "Embeds competencies each session",
    22: "Notices changes in child's behaviour",
    23: "Signposts players to appropriate support (IP/VEO)",
    24: "Critical thinker who checks and challenges",
    25: "Manages other staff supporting sessions",
    26: "Listens and suspends judgement",
    27: "Has a recognised coaching cell (in club)",
    28: "Watches other coaches inside the club",
    29: "Embeds physical development",
    30: "Makes practice competitive & realistic",
    31: "Develops players physically through design",
    32: "Drives intensity using coaching strategies",
    33: "Reports issues using MyConcern appropriately",
    34: "Comfortable challenging poor practice",
    35: "Ambassador of MK Dons",
    36: "Has clear interests away from coaching"
}

# ===================== HELPERS =====================
def get_colour(score):
    if score >= 3.25:
        return "#4CAF50"
    elif score >= 2.51:
        return "#FFD966"
    elif score >= 1.75:
        return "#F4A261"
    else:
        return "#FF6B6B"


def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return pd.read_excel(io.BytesIO(decoded), header=None)


def split_blocks(raw_df):
    block_dfs = []
    header_rows = raw_df[raw_df.apply(
        lambda row: row.astype(str).str.strip().str.lower().eq("full name").any(),
        axis=1
    )].index.tolist()

    for i, start in enumerate(header_rows):
        end = header_rows[i + 1] if i + 1 < len(header_rows) else len(raw_df)
        block = raw_df.iloc[start:end].copy()
        block.columns = block.iloc[0].astype(str).str.strip()
        block = block[1:]
        block = block.dropna(how='all')
        block_dfs.append(block.reset_index(drop=True))

    return block_dfs

# ===================== FILE UPLOAD =====================
@app.callback(
    [Output('file-status', 'children'),
     Output('participant-dropdown', 'options'),
     Output('block-dropdown', 'options'),
     Output('compare-block-1', 'options'),
     Output('compare-block-2', 'options')],
    Input('upload-data', 'contents')
)
def handle_upload(contents):
    global blocks, question_cols

    if contents is None:
        return "No file uploaded yet.", [], [], [], []

    raw_df = parse_contents(contents)
    block_list = split_blocks(raw_df)

    score_map = {"YES": 1, "Neither YES or NO": 0.5, "NO": 0}
    blocks = {}

    for i, block in enumerate(block_list, start=1):
        block.columns = block.columns.str.strip()
        question_cols = [c for c in block.columns if str(c).startswith("Q")]

        for col in question_cols:
            block[col] = block[col].map(score_map)

        blocks[f"Block {i}"] = block

    first_block = next(iter(blocks.values()))
    participants = [{'label': n, 'value': n} for n in first_block['Full Name']]
    block_options = [{'label': b, 'value': b} for b in blocks.keys()]

    return "File uploaded successfully!", participants, block_options, block_options, block_options

# ===================== MAIN DASHBOARD =====================
@app.callback(
    [Output('question-chart', 'figure'),
     Output('group-grid', 'children'),
     Output('development-lists', 'children')],
    [Input('participant-dropdown', 'value'),
     Input('block-dropdown', 'value')]
)
def update_dashboard(selected_name, selected_block):
    if selected_name is None or selected_block is None:
        return {}, "", ""

    df = blocks[selected_block]
    person_data = df[df['Full Name'] == selected_name].iloc[0]

    scores = person_data[question_cols].values

    bar_colors = []
    for s in scores:
        if s == 1:
            bar_colors.append("#4CAF50")
        elif s == 0.5:
            bar_colors.append("#F4A261")
        else:
            bar_colors.append("#FF6B6B")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=question_cols, y=scores, marker_color=bar_colors))
    fig.update_layout(title=f"{selected_name} — {selected_block}",
                      xaxis_title="Questions", yaxis_title="Score",
                      yaxis=dict(range=[0, 1]))

    group_totals = [round(person_data[question_cols[i:i+4]].sum(), 2)
                    for i in range(0, len(question_cols), 4)]

    grid_layout = html.Div([
        html.Div([
            html.Div(f"{score}", style={"fontSize": "28px", "fontWeight": "bold"}),
            html.Div(label, style={"fontSize": "12px"})
        ],
        style={
            "backgroundColor": get_colour(score),
            "padding": "20px",
            "borderRadius": "8px",
            "textAlign": "center",
            "color": "black"
        })
        for label, score in zip(GROUP_LABELS, group_totals)
    ], style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "10px", "marginBottom": "30px"})

    half_scores = []
    zero_scores = []

    for q_col in question_cols:
        q_num = int(q_col.replace("Q", ""))
        score = person_data[q_col]

        if score == 0.5:
            half_scores.append(f"Q{q_num} – {QUESTION_TEXT[q_num]}")
        elif score == 0:
            zero_scores.append(f"Q{q_num} – {QUESTION_TEXT[q_num]}")

    lists_layout = [
        html.Div([
            html.H3("Scored 0.5 (Developing)"),
            html.Ul([html.Li(item) for item in half_scores])
        ], style={"width": "50%"}),

        html.Div([
            html.H3("Scored 0 (Needs Attention)"),
            html.Ul([html.Li(item) for item in zero_scores])
        ], style={"width": "50%"})
    ]

    return fig, grid_layout, lists_layout

# ===================== BLOCK COMPARISON =====================
@app.callback(
    [Output('compare-grid-1', 'children'),
     Output('compare-grid-2', 'children')],
    [Input('participant-dropdown', 'value'),
     Input('compare-block-1', 'value'),
     Input('compare-block-2', 'value')]
)
def update_comparison(selected_name, block1, block2):
    def make_grid(block_name):
        if selected_name is None or block_name is None:
            return ""

        df = blocks[block_name]
        person_data = df[df['Full Name'] == selected_name].iloc[0]

        group_totals = [round(person_data[question_cols[i:i+4]].sum(), 2)
                        for i in range(0, len(question_cols), 4)]

        return html.Div([
            html.Div([
                html.Div(f"{score}", style={"fontSize": "26px", "fontWeight": "bold"}),
                html.Div(label, style={"fontSize": "11px"})
            ],
            style={
                "backgroundColor": get_colour(score),
                "padding": "18px",
                "borderRadius": "8px",
                "textAlign": "center",
                "color": "black"
            })
            for label, score in zip(GROUP_LABELS, group_totals)
        ], style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "10px", "marginTop": "15px"})

    return make_grid(block1), make_grid(block2)
