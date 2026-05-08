"""Review PDF generation — uses reportlab directly, no xhtml2pdf."""
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
import io

def generate_personalized_review_pdf(wrong_questions: list, user_name: str = "Student") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Personalized Review Sheet — {user_name}", styles['Title']))
    story.append(Spacer(1, 0.5*cm))

    if not wrong_questions:
        story.append(Paragraph("No wrong questions yet. Keep practicing!", styles['Normal']))
    else:
        for i, q in enumerate(wrong_questions, 1):
            story.append(Paragraph(f"Q{i}: {q.get('question_text', '')}", styles['Heading3']))
            story.append(Paragraph(f"A) {q.get('option_a', '')}", styles['Normal']))
            story.append(Paragraph(f"B) {q.get('option_b', '')}", styles['Normal']))
            story.append(Paragraph(f"C) {q.get('option_c', '')}", styles['Normal']))
            story.append(Paragraph(f"D) {q.get('option_d', '')}", styles['Normal']))
            story.append(Paragraph(f"✓ Correct Answer: {q.get('correct_answer', '')}", styles['Normal']))
            story.append(Paragraph(f"Explanation: {q.get('explanation', '')}", styles['Normal']))
            story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    return buffer.getvalue()
