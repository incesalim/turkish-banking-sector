"""
Automated Report Generation System

Creates comprehensive PDF and HTML reports for banking sector analysis.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path
import sys
from jinja2 import Template
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))
from config import *


class BankingReportGenerator:
    """Generate comprehensive banking sector reports"""

    def __init__(self, output_dir=None):
        """
        Initialize report generator

        Args:
            output_dir: Directory for saving reports
        """
        self.output_dir = output_dir or REPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        logger.add(
            LOGS_DIR / "report_generator_{time}.log",
            rotation="1 day",
            level="INFO"
        )

        # Setup matplotlib style
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")

    def generate_comprehensive_report(self, data, analysis_results, format='pdf'):
        """
        Generate comprehensive banking sector report

        Args:
            data: DataFrame with banking data
            analysis_results: Dictionary with analysis results
            format: Output format ('pdf', 'html', 'excel')

        Returns:
            Path to generated report
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_name = f"banking_sector_report_{timestamp}"

        if format == 'pdf':
            return self.generate_pdf_report(data, analysis_results, report_name)
        elif format == 'html':
            return self.generate_html_report(data, analysis_results, report_name)
        elif format == 'excel':
            return self.generate_excel_report(data, analysis_results, report_name)
        else:
            logger.error(f"Unsupported format: {format}")
            return None

    def generate_pdf_report(self, data, analysis_results, report_name):
        """
        Generate PDF report

        Args:
            data: Banking data
            analysis_results: Analysis results
            report_name: Report filename

        Returns:
            Path to PDF file
        """
        output_path = self.output_dir / f"{report_name}.pdf"
        doc = SimpleDocTemplate(str(output_path), pagesize=A4)
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2e5c8a'),
            spaceAfter=12,
            spaceBefore=12
        )

        # Title
        title = Paragraph("Turkish Banking Sector Analysis Report", title_style)
        story.append(title)

        # Date
        date_text = Paragraph(
            f"Report Date: {datetime.now().strftime('%B %d, %Y')}",
            styles['Normal']
        )
        story.append(date_text)
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("Executive Summary", heading_style))
        summary_text = self._generate_executive_summary(analysis_results)
        story.append(Paragraph(summary_text, styles['Normal']))
        story.append(Spacer(1, 15))

        # Key Metrics Table
        story.append(Paragraph("Key Performance Indicators", heading_style))
        kpi_table = self._create_kpi_table(analysis_results)
        story.append(kpi_table)
        story.append(Spacer(1, 20))

        # Asset Quality Section
        story.append(PageBreak())
        story.append(Paragraph("Asset Quality Analysis", heading_style))
        if 'asset_quality' in analysis_results:
            asset_text = self._format_analysis_section(analysis_results['asset_quality'])
            story.append(Paragraph(asset_text, styles['Normal']))
            story.append(Spacer(1, 10))

        # Charts
        if not data.empty:
            # NPL Trend Chart
            npl_chart = self._create_npl_chart(data)
            if npl_chart:
                story.append(npl_chart)
                story.append(Spacer(1, 15))

        # Profitability Section
        story.append(PageBreak())
        story.append(Paragraph("Profitability Analysis", heading_style))
        if 'profitability' in analysis_results:
            profit_text = self._format_analysis_section(analysis_results['profitability'])
            story.append(Paragraph(profit_text, styles['Normal']))
            story.append(Spacer(1, 10))

        # Profitability Chart
        if not data.empty:
            roa_chart = self._create_profitability_chart(data)
            if roa_chart:
                story.append(roa_chart)
                story.append(Spacer(1, 15))

        # Liquidity Section
        story.append(PageBreak())
        story.append(Paragraph("Liquidity Analysis", heading_style))
        if 'liquidity' in analysis_results:
            liquidity_text = self._format_analysis_section(analysis_results['liquidity'])
            story.append(Paragraph(liquidity_text, styles['Normal']))

        # Capital Section
        story.append(PageBreak())
        story.append(Paragraph("Capital Adequacy Analysis", heading_style))
        if 'capital' in analysis_results:
            capital_text = self._format_analysis_section(analysis_results['capital'])
            story.append(Paragraph(capital_text, styles['Normal']))

        # Alerts and Recommendations
        if analysis_results.get('all_alerts'):
            story.append(PageBreak())
            story.append(Paragraph("Alerts and Recommendations", heading_style))
            alerts_text = self._format_alerts(analysis_results['all_alerts'])
            story.append(Paragraph(alerts_text, styles['Normal']))

        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")

        return output_path

    def generate_html_report(self, data, analysis_results, report_name):
        """
        Generate HTML report

        Args:
            data: Banking data
            analysis_results: Analysis results
            report_name: Report filename

        Returns:
            Path to HTML file
        """
        output_path = self.output_dir / f"{report_name}.html"

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Turkish Banking Sector Analysis Report</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .header {
                    background-color: #1f4788;
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 5px;
                }
                .section {
                    background-color: white;
                    margin: 20px 0;
                    padding: 25px;
                    border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h2 {
                    color: #2e5c8a;
                    border-bottom: 2px solid #2e5c8a;
                    padding-bottom: 10px;
                }
                .kpi-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }
                .kpi-card {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                }
                .kpi-value {
                    font-size: 32px;
                    font-weight: bold;
                }
                .kpi-label {
                    font-size: 14px;
                    opacity: 0.9;
                }
                .alert {
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 10px 0;
                }
                .metric-table {
                    width: 100%;
                    border-collapse: collapse;
                }
                .metric-table th, .metric-table td {
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                .metric-table th {
                    background-color: #2e5c8a;
                    color: white;
                }
                .metric-table tr:hover {
                    background-color: #f5f5f5;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Turkish Banking Sector Analysis Report</h1>
                <p>{{ report_date }}</p>
            </div>

            <div class="section">
                <h2>Executive Summary</h2>
                <p>{{ executive_summary }}</p>
                <p><strong>Overall Health Score:</strong> {{ health_score }}/100</p>
            </div>

            <div class="section">
                <h2>Key Performance Indicators</h2>
                <div class="kpi-grid">
                    {{ kpi_cards }}
                </div>
            </div>

            <div class="section">
                <h2>Asset Quality</h2>
                {{ asset_quality_section }}
            </div>

            <div class="section">
                <h2>Profitability</h2>
                {{ profitability_section }}
            </div>

            <div class="section">
                <h2>Liquidity</h2>
                {{ liquidity_section }}
            </div>

            <div class="section">
                <h2>Capital Adequacy</h2>
                {{ capital_section }}
            </div>

            {% if alerts %}
            <div class="section">
                <h2>Alerts and Recommendations</h2>
                {{ alerts }}
            </div>
            {% endif %}

            <div class="section">
                <p style="text-align: center; color: #666;">
                    Report generated on {{ report_date }}<br>
                    BDDK Banking Sector Analysis System
                </p>
            </div>
        </body>
        </html>
        """

        # Prepare template data
        template_data = {
            'report_date': datetime.now().strftime('%B %d, %Y at %H:%M'),
            'executive_summary': self._generate_executive_summary(analysis_results),
            'health_score': analysis_results.get('overall_health', 'N/A'),
            'kpi_cards': self._generate_kpi_cards_html(analysis_results),
            'asset_quality_section': self._format_html_section(analysis_results.get('asset_quality', {})),
            'profitability_section': self._format_html_section(analysis_results.get('profitability', {})),
            'liquidity_section': self._format_html_section(analysis_results.get('liquidity', {})),
            'capital_section': self._format_html_section(analysis_results.get('capital', {})),
            'alerts': self._format_alerts_html(analysis_results.get('all_alerts', []))
        }

        # Render template
        template = Template(html_template)
        html_content = template.render(**template_data)

        # Save HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML report generated: {output_path}")
        return output_path

    def generate_excel_report(self, data, analysis_results, report_name):
        """
        Generate Excel report with multiple sheets

        Args:
            data: Banking data
            analysis_results: Analysis results
            report_name: Report filename

        Returns:
            Path to Excel file
        """
        output_path = self.output_dir / f"{report_name}.xlsx"

        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            workbook = writer.book

            # Format styles
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#2e5c8a',
                'font_color': 'white',
                'border': 1
            })

            # Summary Sheet
            summary_df = self._create_summary_dataframe(analysis_results)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Raw Data Sheet
            if not data.empty:
                data.to_excel(writer, sheet_name='Raw Data', index=False)

            # Metrics Sheet
            metrics_df = self._create_metrics_dataframe(analysis_results)
            metrics_df.to_excel(writer, sheet_name='Key Metrics', index=False)

            # Alerts Sheet
            if analysis_results.get('all_alerts'):
                alerts_df = pd.DataFrame({
                    'Alert': analysis_results['all_alerts']
                })
                alerts_df.to_excel(writer, sheet_name='Alerts', index=False)

        logger.info(f"Excel report generated: {output_path}")
        return output_path

    # Helper methods
    def _generate_executive_summary(self, analysis_results):
        """Generate executive summary text"""
        health_score = analysis_results.get('overall_health', 0)
        alert_count = len(analysis_results.get('all_alerts', []))

        summary = f"The Turkish banking sector shows an overall health score of {health_score}/100. "

        if alert_count == 0:
            summary += "No significant alerts detected. The sector demonstrates stable performance across all key metrics."
        elif alert_count <= 3:
            summary += f"Analysis identified {alert_count} areas requiring attention. "
        else:
            summary += f"Analysis identified {alert_count} alerts requiring management attention. "

        return summary

    def _create_kpi_table(self, analysis_results):
        """Create KPI table for PDF"""
        data = []

        # Extract key metrics
        if 'asset_quality' in analysis_results:
            aq = analysis_results['asset_quality'].get('metrics', {})
            if 'current_npl_ratio' in aq:
                data.append(['NPL Ratio', f"{aq['current_npl_ratio']:.2f}%"])

        if 'profitability' in analysis_results:
            prof = analysis_results['profitability'].get('metrics', {})
            if 'current_roa' in prof:
                data.append(['ROA', f"{prof['current_roa']:.2f}%"])
            if 'current_roe' in prof:
                data.append(['ROE', f"{prof['current_roe']:.2f}%"])

        if 'capital' in analysis_results:
            cap = analysis_results['capital'].get('metrics', {})
            if 'current_car' in cap:
                data.append(['Capital Adequacy Ratio', f"{cap['current_car']:.2f}%"])

        if not data:
            data = [['No metrics available', '']]

        table = Table([['Metric', 'Value']] + data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        return table

    def _format_analysis_section(self, section_data):
        """Format analysis section for PDF"""
        text = ""

        if 'metrics' in section_data:
            text += "<br/>".join([f"{k}: {v}" for k, v in section_data['metrics'].items()])

        if 'alerts' in section_data and section_data['alerts']:
            text += "<br/><br/><b>Alerts:</b><br/>"
            text += "<br/>".join([f"• {alert}" for alert in section_data['alerts']])

        return text if text else "No data available"

    def _format_alerts(self, alerts):
        """Format alerts for PDF"""
        if not alerts:
            return "No alerts"

        return "<br/>".join([f"• {alert}" for alert in alerts])

    def _create_npl_chart(self, data):
        """Create NPL chart for PDF"""
        if 'npl_ratio' not in data.columns:
            return None

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(data.index, data['npl_ratio'], marker='o')
        ax.set_title('NPL Ratio Trend')
        ax.set_xlabel('Period')
        ax.set_ylabel('NPL Ratio (%)')
        ax.grid(True, alpha=0.3)

        # Save to bytes
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()

        return Image(img_buffer, width=5*inch, height=3*inch)

    def _create_profitability_chart(self, data):
        """Create profitability chart for PDF"""
        if 'roa' not in data.columns and 'roe' not in data.columns:
            return None

        fig, ax = plt.subplots(figsize=(6, 4))

        if 'roa' in data.columns:
            ax.plot(data.index, data['roa'], marker='o', label='ROA')
        if 'roe' in data.columns:
            ax.plot(data.index, data['roe'], marker='s', label='ROE')

        ax.set_title('Profitability Metrics')
        ax.set_xlabel('Period')
        ax.set_ylabel('Return (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()

        return Image(img_buffer, width=5*inch, height=3*inch)

    def _generate_kpi_cards_html(self, analysis_results):
        """Generate KPI cards HTML"""
        cards = []

        # Add KPI cards based on available data
        if 'asset_quality' in analysis_results:
            metrics = analysis_results['asset_quality'].get('metrics', {})
            if 'current_npl_ratio' in metrics:
                cards.append(f"""
                <div class="kpi-card">
                    <div class="kpi-label">NPL Ratio</div>
                    <div class="kpi-value">{metrics['current_npl_ratio']:.2f}%</div>
                </div>
                """)

        return ''.join(cards) if cards else '<p>No KPI data available</p>'

    def _format_html_section(self, section_data):
        """Format section for HTML"""
        html = '<table class="metric-table"><tr><th>Metric</th><th>Value</th></tr>'

        if 'metrics' in section_data:
            for key, value in section_data['metrics'].items():
                html += f'<tr><td>{key}</td><td>{value}</td></tr>'

        html += '</table>'
        return html

    def _format_alerts_html(self, alerts):
        """Format alerts for HTML"""
        if not alerts:
            return '<p>No alerts</p>'

        html = ''.join([f'<div class="alert">{alert}</div>' for alert in alerts])
        return html

    def _create_summary_dataframe(self, analysis_results):
        """Create summary DataFrame for Excel"""
        summary_data = {
            'Metric': ['Overall Health Score', 'Total Alerts', 'Report Date'],
            'Value': [
                analysis_results.get('overall_health', 'N/A'),
                len(analysis_results.get('all_alerts', [])),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        return pd.DataFrame(summary_data)

    def _create_metrics_dataframe(self, analysis_results):
        """Create metrics DataFrame for Excel"""
        metrics_list = []

        for category in ['asset_quality', 'profitability', 'liquidity', 'capital']:
            if category in analysis_results:
                cat_metrics = analysis_results[category].get('metrics', {})
                for metric, value in cat_metrics.items():
                    metrics_list.append({
                        'Category': category.replace('_', ' ').title(),
                        'Metric': metric.replace('_', ' ').title(),
                        'Value': value
                    })

        return pd.DataFrame(metrics_list) if metrics_list else pd.DataFrame()


def main():
    """Example usage"""
    generator = BankingReportGenerator()

    # Sample analysis results
    sample_results = {
        'overall_health': 85,
        'all_alerts': ['NPL ratio increasing', 'Low ROA'],
        'asset_quality': {
            'metrics': {'current_npl_ratio': 3.8, 'avg_npl_ratio': 3.5},
            'alerts': ['NPL ratio increasing']
        },
        'profitability': {
            'metrics': {'current_roa': 1.3, 'current_roe': 13.0},
            'alerts': ['Low ROA']
        }
    }

    # Generate reports
    sample_data = pd.DataFrame()  # Empty for demo

    pdf_path = generator.generate_pdf_report(sample_data, sample_results, 'test_report')
    html_path = generator.generate_html_report(sample_data, sample_results, 'test_report')

    print(f"PDF Report: {pdf_path}")
    print(f"HTML Report: {html_path}")


if __name__ == "__main__":
    main()
