import os
from datetime import datetime
import datetime as dt_mod
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class PDFService:
    @staticmethod
    def generate_agreement(chat, post, poster, worker):
        # Ensure static/agreements directory exists
        os.makedirs("static/agreements", exist_ok=True)
        filename = f"{chat['id']}_agreement.pdf"
        filepath = os.path.join("static/agreements", filename)
        
        # Setup document
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Premium Slate-themed design
        title_style = ParagraphStyle(
            name='TitleStyle',
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A'),  # Slate 900
            alignment=1,  # Centered
            spaceAfter=25
        )
        
        header_style = ParagraphStyle(
            name='HeaderStyle',
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#475569'),  # Slate 600
            spaceBefore=12,
            spaceAfter=6
        )
        
        normal_style = ParagraphStyle(
            name='NormalStyle',
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#1E293B'),  # Slate 800
            spaceAfter=6
        )
        
        italic_style = ParagraphStyle(
            name='ItalicStyle',
            fontName='Helvetica-Oblique',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#64748B'),  # Slate 500
            spaceAfter=6
        )
        
        story = []
        
        # Title
        story.append(Paragraph("NEIGHBOURLY JOB AGREEMENT", title_style))
        story.append(Spacer(1, 10))
        
        # Fields
        story.append(Paragraph(f"<b>Task:</b> {post.get('title', 'N/A')}", normal_style))
        story.append(Paragraph(f"<b>Category:</b> {post.get('post_category', 'N/A')}", normal_style))
        story.append(Spacer(1, 8))
        
        story.append(Paragraph(f"<b>Poster:</b> {poster.get('name', 'N/A')}", normal_style))
        story.append(Paragraph(f"<b>Worker:</b> {worker.get('name', 'N/A')}", normal_style))
        story.append(Spacer(1, 8))
        
        agreed_pay = chat.get('agreed_pay')
        story.append(Paragraph(f"<b>Agreed Pay:</b> ₹{agreed_pay if agreed_pay is not None else 'N/A'} per day", normal_style))
        
        # Ensure work_date is formatted if it's a date or datetime object
        work_date = chat.get('work_date')
        if isinstance(work_date, (datetime, dt_mod.date)):
            work_date_str = work_date.strftime('%Y-%m-%d')
        else:
            work_date_str = str(work_date) if work_date else 'N/A'
            
        story.append(Paragraph(f"<b>Work Date:</b> {work_date_str}", normal_style))
        story.append(Paragraph(f"<b>Time Slot:</b> {chat.get('work_time_slot', 'N/A')}", normal_style))
        
        area_name = post.get('area_name') or 'N/A'
        district = post.get('district') or 'N/A'
        story.append(Paragraph(f"<b>Location:</b> {area_name}, {district}", normal_style))
        story.append(Spacer(1, 12))
        
        # Description
        story.append(Paragraph("<b>Task Description:</b>", header_style))
        description = post.get('description') or 'No description provided.'
        description_formatted = description.replace('\n', '<br/>')
        story.append(Paragraph(description_formatted, normal_style))
        story.append(Spacer(1, 20))
        
        # Footer agreement
        story.append(Paragraph("Both parties agreed to these terms through Neighbourly platform.", italic_style))
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        story.append(Paragraph(f"Agreement generated on: {now_str} UTC", italic_style))
        
        doc.build(story)
        
        return f"/static/agreements/{filename}"
