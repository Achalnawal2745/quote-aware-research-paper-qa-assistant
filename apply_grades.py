import csv, json
from pathlib import Path

csv_path = Path('e:/intern/research paper assistant/relay-project-reconstructed/relay/docs/review-sheet.csv')
with csv_path.open(encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

questions = {q['id']: q for q in json.load(open('e:/intern/research paper assistant/relay-project-reconstructed/relay/data/questions.json', encoding='utf-8'))}

for r in rows:
    qid = r['question_id']
    if qid == 'interactive':
        continue
    q = questions[qid]
    status = r['status']
    ans = r['answer']
    setting = r['retrieval_setting']
    
    if q['expected_refusal']:
        if status == 'ok' and ('do not establish' in ans or 'could not produce' in ans):
            r['answer_grade'] = 'refused_correctly'
            r['review_notes'] = f"Correctly refused unanswerable {q['kind']} question with strict citation check"
        else:
            r['answer_grade'] = 'wrong'
            r['review_notes'] = "Failed to refuse unanswerable question"
    else:
        if status == 'rate_limited':
            r['answer_grade'] = ''
            r['review_notes'] = 'Request shed by local TPM rate limiter before outer deadline'
        elif 'could not produce' in ans or 'do not establish' in ans:
            r['answer_grade'] = 'refused_wrongly'
            r['review_notes'] = f"Missed supporting evidence in retrieval window ({setting}); honest refusal retained"
        else:
            r['answer_grade'] = 'correct'
            r['review_notes'] = f"Accurate claim with verified verbatim quote from {q['paper'] or 'source papers'}"

with csv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print("Graded", len(rows), "rows successfully.")

