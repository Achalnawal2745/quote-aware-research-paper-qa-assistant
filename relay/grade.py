
"""Export manual review sheets or apply evidence-checked human grades.

The original source CSV is never modified.
"""

import argparse
import csv
from pathlib import Path


VALID = {
    "correct",
    "wrong",
    "refused_correctly",
    "refused_wrongly"
}

REVIEW_FIELDS = [
    "request_id",
    "question_id",
    "retrieval_setting",
    "source",
    "status",
    "answer",
    "answer_grade",
    "review_notes"
]


def read_csv(path):
    """Read a CSV file and return its headers and rows."""

    with Path(path).open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"CSV is empty or has no header: {path}")

        return list(reader.fieldnames), list(reader)


def write_csv(path, fields, rows):
    """Write CSV output without modifying the source file."""

    with Path(path).open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)


def validate_source(fields):
    """Check that the source CSV has the required columns."""

    required = {
        "request_id",
        "question_id",
        "retrieval_setting",
        "source",
        "status",
        "answer",
        "answer_grade"
    }

    missing = required - set(fields)

    if missing:
        raise ValueError(
            "Source CSV is missing required columns: "
            + ", ".join(sorted(missing))
        )


def export_review_sheet(rows, output):
    """Export only real API responses for manual grading."""

    review_rows = [
        {
            field: row.get(field, "")
            for field in REVIEW_FIELDS
        }
        for row in rows
        if row.get("source") == "real"
    ]

    write_csv(
        output,
        REVIEW_FIELDS,
        review_rows
    )


def load_grades(path):
    """Load and validate the manual grading CSV."""

    fields, rows = read_csv(path)

    required = {
        "request_id",
        "answer_grade",
        "review_notes"
    }

    missing = required - set(fields)

    if missing:
        raise ValueError(
            "Grades CSV is missing required columns: "
            + ", ".join(sorted(missing))
        )

    grades = {}

    for row in rows:
        request_id = (row.get("request_id") or "").strip()

        if not request_id:
            continue

        if request_id in grades:
            raise ValueError(
                f"Duplicate request_id in grades CSV: {request_id}"
            )

        grades[request_id] = row

    return grades


def apply_grades(source_fields, rows, grades):
    """Apply valid human grades to real API responses."""

    updated_rows = []

    for row in rows:

        updated = dict(row)

        request_id = (row.get("request_id") or "").strip()
        grade = grades.get(request_id)

        if not grade:
            updated_rows.append(updated)
            continue

        answer_grade = (
            grade.get("answer_grade") or ""
        ).strip()

        if not answer_grade:
            updated_rows.append(updated)
            continue

        if row.get("source") != "real":
            raise ValueError(
                f"Cannot quality-grade non-real output: {request_id}"
            )

        if answer_grade not in VALID:
            raise ValueError(
                f"Invalid grade '{answer_grade}' "
                f"for request_id {request_id}"
            )

        review_notes = (
            grade.get("review_notes") or ""
        ).strip()

        if not review_notes:
            raise ValueError(
                f"Missing evidence review_notes "
                f"for request_id {request_id}"
            )

        updated["answer_grade"] = answer_grade

        updated_rows.append(updated)

    return updated_rows


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Export a manual review sheet or apply "
            "evidence-checked human grades."
        )
    )

    parser.add_argument(
        "csv",
        help="Source results CSV"
    )

    parser.add_argument(
        "--grades",
        help="CSV containing completed human grades"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path"
    )

    args = parser.parse_args()

    source_fields, rows = read_csv(args.csv)

    validate_source(source_fields)

    if args.grades:

        grades = load_grades(args.grades)

        updated_rows = apply_grades(
            source_fields,
            rows,
            grades
        )

        write_csv(
            args.output,
            source_fields,
            updated_rows
        )

    else:

        export_review_sheet(
            rows,
            args.output
        )

    print(args.output)


if __name__ == "__main__":
    main()
