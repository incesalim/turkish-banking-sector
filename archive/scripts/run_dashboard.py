"""
Launch Professional BDDK Dashboard

Simple launcher for the enterprise-grade dashboard.
"""

from visualizations.professional_dashboard import ProfessionalBankingDashboard


def main():
    """Launch the dashboard"""
    print("\n" + "="*70)
    print(" "*20 + "BDDK BANKING ANALYSIS")
    print(" "*15 + "Professional Dashboard v2.0")
    print("="*70)
    print("\n🚀 Starting dashboard...")
    print("📊 Loading data from database...")
    print("\n" + "="*70)

    dashboard = ProfessionalBankingDashboard()
    dashboard.run(debug=True, port=8050)


if __name__ == "__main__":
    main()
