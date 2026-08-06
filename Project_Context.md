# Trading Research Toolkit
Version: 1.0
Author: Prashant + ChatGPT
Language: Python
Goal: Evidence-based research of candlestick patterns in Indian stock markets.

---

# Project Vision

This project is NOT a trading bot.

This project is NOT an auto-buy/sell system.

This project is a statistical research framework that evaluates whether technical analysis patterns actually provide an edge.

The objective is to answer questions like:

• Does Bullish Engulfing actually work?
• Does Bearish Engulfing actually work?
• Does Volume improve probability?
• Does Trend matter?
• Does Confirmation matter?
• Which timeframe performs best?
• Which sectors perform best?
• Which candlestick patterns are statistically useful?
• What is the actual win rate instead of relying on opinions?

The entire project should remain objective and data-driven.

No assumptions.

Only statistics.

---

# Project Philosophy

Never trust YouTube.

Never trust books blindly.

Never trust a single chart.

Everything should be proven using historical data.

Every conclusion must come from thousands of historical examples.

---

# Development Style

The project must be written like production-quality software.

Requirements:

- Modular architecture
- Clean code
- Functions should have one responsibility
- Well documented
- Easy to extend
- No duplicate code
- Use type hints where appropriate
- Use classes only when they improve clarity
- Prefer readable code over clever code

---

# Tech Stack

Python 3.12+

Libraries

pandas
numpy
yfinance (prototype only)
mplfinance
plotly
tqdm
openpyxl

Later

TA-Lib
vectorbt
backtesting.py

---

# Folder Structure

TradingResearch/

    config.py

    main.py

    requirements.txt

    data/

        downloader.py

    patterns/

        bullish_engulfing.py

        bearish_engulfing.py

        hammer.py

        inverted_hammer.py

        shooting_star.py

    analysis/

        trend.py

        confirmation.py

        support_resistance.py

        statistics.py

    charts/

    reports/

    datasets/

---

# Current Phase

Phase 1

Only implement

Bullish Engulfing

Timeframe

Daily

Universe

Initially a few stocks for testing.

Later

NIFTY 500.

---

# Bullish Engulfing Rules

Current candle must be GREEN.

Previous candle must be RED.

Current Open < Previous Close

Current Close > Previous Open

Body must completely engulf previous body.

Ignore shadows.

---

# Trend Filter

A Bullish Engulfing should only be considered if a prior downtrend exists.

Current definition:

Previous five candles should generally make lower highs and lower lows.

The trend module should be isolated so that better definitions can replace it later.

---

# Confirmation Rule

Confirmation candle

The next candle should close above the engulfing candle high.

Store

Confirmed = True

or

Confirmed = False

---

# Success Definition

Success is NOT simply the next candle being green.

Current definition

Entry

High of engulfing candle after confirmation.

Stop Loss

Low of engulfing candle.

Target

2R

A trade succeeds if 2R is reached before the stop-loss within the next five trading days.

This definition should be configurable.

---

# Statistics Required

Total Patterns

Wins

Losses

Win Rate

Average Return

Average Drawdown

Average Holding Period

Maximum Favorable Excursion (MFE)

Maximum Adverse Excursion (MAE)

Volume Comparison

Trend Strength

Sector Performance

Year-wise Performance

Month-wise Performance

---

# CSV Output

Each detected pattern should save

Date

Ticker

Open

High

Low

Close

Volume

Previous Trend

Confirmed

Entry

Stop

Target

Maximum Gain

Maximum Loss

Win

Notes

---

# Future Features

Bearish Engulfing

Hammer

Inverted Hammer

Shooting Star

Morning Star

Evening Star

Doji

Harami

Three White Soldiers

Three Black Crows

---

# Future Filters

200 EMA

50 EMA

VWAP

ATR

ADX

RSI

MACD

Gap Analysis

Support

Resistance

Sector Trend

Index Trend

Volume Profile

---

# Charts

Eventually every detected pattern should automatically save an image.

Example

charts/

Bullish/

Reliance_2024-05-10.png

Infosys_2022-11-08.png

etc.

---

# Reports

Generate

CSV

Excel

Interactive HTML

Eventually PDF

---

# Long-Term Goal

Eventually this toolkit should become a complete candlestick research framework capable of answering statistically whether a technical pattern has an edge.

Every conclusion must be supported by historical evidence.

Never hardcode assumptions.

Everything should be configurable.

---

# Coding Instructions for AI

When generating code:

- Never generate one giant script.
- Build one module at a time.
- Explain architectural decisions.
- Prefer maintainability over short code.
- Ensure every module is independently testable.
- Add docstrings.
- Handle errors gracefully.
- Avoid unnecessary dependencies.
- Keep functions small and focused.
- Ask before making major architectural changes.

---

# Immediate Next Task

Create the project foundation:

1. config.py
2. requirements.txt
3. downloader.py
4. main.py

Then implement historical data download for a small set of stocks.

After that, implement Bullish Engulfing detection.

Only proceed to trend analysis after the pattern detection is verified.