"""Generate an explicitly unfinished two-page report, never a fabricated final submission."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from pypdf import PdfReader

OUT='docs/writeup-draft.pdf'
P=ParagraphStyle('p',fontName='Helvetica',fontSize=8,leading=10,spaceAfter=4)
H=ParagraphStyle('h',parent=P,fontName='Helvetica-Bold',fontSize=9,leading=11,spaceBefore=5,spaceAfter=3,textColor=colors.HexColor('#123c55'))
C=ParagraphStyle('cell',fontName='Helvetica',fontSize=6.5,leading=8)
T=ParagraphStyle('title',parent=H,fontSize=16,leading=19)
story=[]
def para(text,style=P): story.append(Paragraph(escape(text),style))
def heading(text): para(text,H)

def get_table(label):
    text=Path('docs/generated-tables.md').read_text()
    lines=text.split(label,1)[1].splitlines()
    rows=[]
    for line in lines:
        if line.startswith('|'):
            cells=[c.strip() for c in line.strip('|').split('|')]
            if all(set(c)<=set('-: ') for c in cells): continue
            rows.append(cells)
        elif rows: break
    return rows

def table(label,widths=None):
    rows=get_table(label)
    t=Table([[Paragraph(escape(c),C) for c in r] for r in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6eff3')),
                          ('VALIGN',(0,0),(-1,-1),'TOP'),
                          ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#9db5c1')),
                          ('LINEBELOW',(0,1),(-1,-1),.2,colors.HexColor('#dce4e8')),
                          ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
                          ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    story.append(t);story.append(Spacer(1,4))

para('The Relay | implementation draft',T)
para('NOT READY TO SUBMIT: all bundled model results are synthetic, with assumed service parameters. Real calibration, real quality grading and candidate reflection remain pending.')
heading('1. What I built and why.')
para('Python async QA: admission, heuristic query analysis, BM25 retrieval, cited JSON draft, deterministic validation, optional model verification, and one bounded evidence-expansion/repair branch. The shaping decision is bounded waiting and evidence checks rather than accepting unlimited work. No claim of semantic safety follows from quote matching alone.')
heading('2. The real service and my stand-in.')
para('The pinned paper versions are locally extracted with page provenance and SHA-256 hashes. Public Groq documentation was checked, but account limits and hosted behavior are not yet measured. The HTTP stand-in shares the client adapter, emits SSE, usage and quota headers, and injects transient failures, slow success, concurrency slowdown and daily exhaustion. Its current parameters are assumptions, not fitted observations.')
table('## Table 1:',[90,90,260,91])
heading('3. Results.')
para('Times below are milliseconds; percentiles are p50 / p95 / p99 for successful requests only. Duration is the arrival window; burst rate is an instantaneous batch. Table outcomes cover every request. Synthetic tokens use a heuristic, quality grades are blank, and zero cost means actual synthetic cash charge. Small-sample tail estimates are unstable.')
table('## Table 2a:',[86,40,31,43,58,137,136])
table('## Table 2b:',[86,32,44,50,49,42,69,98,61])
heading('4. Where the time goes.')
# Slow request text is already derived from CSV; keep exact quantitative breakdown in a table.
import csv
rows=list(csv.DictReader(open('results.csv')))
slow=max((r for r in rows if r['status']=='ok'),key=lambda r:float(r['total_ms']))
values=[['Slow request','Queue/budget ms','Working ms','Retry wait ms','User first ms','Total ms'],
        [slow['request_id']]+[f'{float(slow[k]):.1f}' for k in ['queue_wait_ms','working_ms','retry_wait_ms','first_token_ms','total_ms']]]
t=Table([[Paragraph(escape(v),C) for v in r] for r in values],colWidths=[106,85,85,85,85,85]);story.append(t)
para('The matching events trace separates queue/budget waiting, model/retrieval work and retry waiting. Residual scheduling overhead is reported in generated-tables.md. Almost all delay precedes release because answers are buffered. Provider TTFT and the additional release hold are separately retained in the CSV; the hold is not purely verifier overhead.')
heading('5. When a limit is hit.')
para('Minute limits cause bounded waiting only when recovery fits the user deadline, otherwise rejection. Daily exhaustion stops new calls and futile retries. Observed headers tighten local budgets. Normal QA reduces initial context near quota pressure; quality experiments retain their setting. No reset at local midnight is assumed. The ledger is single-process, not a distributed limiter.')
story.append(PageBreak())
heading('Retrieval: quality versus cost.')
para('Settings use whitespace words with overlap, not model tokens: small, medium and large differ in passage size and fetched count, without reranking. All comparisons below await real hosted answers and human evidence review. No winning setting is claimed. See generated-tables.md for exact settings. Passage reduction is logged when used outside the fixed-setting quality experiment.')
table('## Table 3:',[74,40,65,40,65,58,65,65,59])
heading('How this library will mislead a naive retriever.')
para('Learned chunking is not RAG passage splitting: ask whether H-Net proves our retrieval chunk size is better. Flattened equations and tables lose layout: ask which Moshi training phase each acoustic delay belongs to. Related work describes other systems: ask whether the AudioPaLM paragraph means Moshi initializes from PaLM. Exact source pages and inspected examples are in extraction-audit.md; these hazards are not measured failure rates.')
heading('6. Retries.')
para('Only eligible transient failures receive bounded backoff with jitter, respecting Retry-After and the remaining deadline. Daily exhaustion is not retried. The retry-disabled and retry-enabled rows above show an observed case where retries reduced completions and introduced abandonment. This is a small seeded simulator comparison; retrying changes fault draw order, so it is not a paired causal experiment.')
heading('7. What the person sees.')
para('If the daily allowance is gone: “The daily model allowance is exhausted. I cannot generate and validate an answer now. Please try after the provider allowance recovers.” The system does not promise an unobserved reset time or quietly substitute an unsupported answer.')
heading("8. What I'm unsure about, what I left out, what I learned.")
para('Candidate reflection pending. Key uncertainty: structural citation validation may pass semantically unsupported claims; manually grade and audit it before choosing the verifier policy. A mistaken assumption breaks groundedness, not just speed. Deliberately omitted: reranking and distributed scheduling. Learning to explain personally: token budgets and request budgets are independent, so a low request rate can still exhaust capacity.')
heading('Your feedback on Vaani.')
para('Draft observation for the candidate to verify personally: the homepage connects building, running and improving voice agents and offers a live-call demo. The phrase “voice AI harness” could be clearer about its boundary versus an orchestration layer. Suggested change: add a short request-lifecycle diagram identifying integrations and responsibilities. Source: https://www.vaani.dev/ (text fetched; no platform or live-call test performed).')
heading('How I worked with the assistant.')
para('INCOMPLETE — attach the actual conversation export separately; conversation-history/README.md is a reminder, not a transcript. Replace this section with your own approximately half-page reflection, using the real history. Do not claim assistant-written implementation or assistant-written questions as exclusively yours.')
para('Three prompts to discuss: the request to explain the real pain points; the user critique separating provider and user-visible TTFT and requiring a common HTTP adapter; and the instruction to build with honest synthetic-versus-real provenance. Explain what each changed, rather than merely listing prompts.')
para('A documented error to inspect: the initial context proposal could exceed the provisional TPM in one call, exposed by budget arithmetic. Another preserved mistake is an exploratory “steady” load that exceeded the assumed quota; its raw run remains separate from the corrected baseline. Confirm that you understand both fixes.')
para('An actual overrule must be supplied by the candidate, not invented. The user already directed several changes to the plan; identify which you deliberately adopted and why, and which choice you independently changed. State your own contribution precisely: question selection, manual PDF checks, policy choice, experimental interpretation or another verifiable action. Before submission, defend and modify the code yourself.')

def footer(canvas,doc):
    canvas.setFont('Helvetica',7);canvas.setFillColor(colors.grey)
    canvas.drawString(32,20,'DRAFT — synthetic evidence only; not a completed submission')
    canvas.drawRightString(A4[0]-32,20,str(doc.page))

SimpleDocTemplate(OUT,pagesize=A4,leftMargin=32,rightMargin=32,topMargin=24,bottomMargin=30).build(story,onFirstPage=footer,onLaterPages=footer)
n=len(PdfReader(OUT).pages)
print(OUT,'pages=',n)
if n!=2:
    raise SystemExit('Draft exceeded two pages; adjust content before delivery')
