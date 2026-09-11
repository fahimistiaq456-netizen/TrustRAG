"""Generate the included synthetic source handbook as a readable PDF."""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

root = Path(__file__).parent
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="HandbookTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=16))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, spaceBefore=10, spaceAfter=5))
story = [Paragraph("Northstar University", styles["HandbookTitle"]), Paragraph("Synthetic Undergraduate Handbook 2026", styles["Normal"]), Spacer(1, 12)]
for heading, body in [("Graduation", "A bachelor's degree requires 120 successfully completed credits and a cumulative grade point average of at least 2.00. Students must complete at least 30 of the 120 credits in residence at Northstar University. Every degree includes a three-credit capstone course."), ("Registration and academic standing", "The normal maximum course load is 18 credits in a semester. A student seeking more than 18 credits must receive approval from the Academic Dean before registration. A student whose cumulative GPA falls below 2.00 is placed on academic warning."), ("Courses and withdrawal", "A prerequisite is satisfied only with a grade of C or higher unless a course description states a higher requirement. A student may withdraw from a course through the end of week 10 of a standard semester. Withdrawals after week 10 are not permitted except where university policy explicitly authorizes an exception."), ("Student support", "Students seeking academic adjustments or disability-related accommodations should contact Accessibility Services before or as soon as practical after the start of a course. A voluntary leave of absence may be approved for up to two consecutive semesters; requests must be submitted to the Registrar.")]:
    story += [Paragraph(heading, styles["Section"]), Paragraph(body, styles["BodyText"])]
SimpleDocTemplate(str(root / "university_handbook.pdf"), pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch, title="Northstar University Handbook").build(story)
