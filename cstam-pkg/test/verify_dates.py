#!/usr/bin/env python3
def test_date_transitions():
    test_dates = [
        (2026, 1, 31), 
        (2026, 2, 28), 
        (2028, 2, 29), 
        (2026, 4, 30), 
    ]
    print(f"{'Simulated Date':<20} | {'Resulting Folder Path':<40}")
    print("-" * 65)
    for y, m, d in test_dates:
        simulated_now = datetime.datetime(y, m, d, 23, 59, 59)
        year_str = simulated_now.strftime("%Y")
        month_str = simulated_now.strftime("%B")
        day_str = simulated_now.strftime("%d")
        print(f"{simulated_now.strftime('%Y-%m-%d'):<20} | .../{year_str}/{month_str}/{day_str}/...")
        next_day = simulated_now + datetime.timedelta(seconds=1)
        n_year = next_day.strftime("%Y")
        n_month = next_day.strftime("%B")
        n_day = next_day.strftime("%d")
        print(f"{next_day.strftime('%Y-%m-%d'):<20} | .../{n_year}/{n_month}/{n_day}/...  <-- NEXT DAY")
        print("-" * 65)
if __name__ == "__main__":
    test_date_transitions()
