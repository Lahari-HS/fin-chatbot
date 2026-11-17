# 💰 Fin-Chatbot: AI Personal Finance Assistant

An AI chatbot that answers questions on budgeting, savings, loans, investing, and financial planning for Indian users.

🔗 **Live app:** https://fin-chatbot-cj7nayrpvxksn3ktfcmtuo.streamlit.app/

## Features
- Plain-language answers on EMI, SIP, emergency funds, credit score, and more
- Calculations done by code, not by the AI, so the numbers are reliable
- Answers grounded in a small knowledge base, with sources shown
- Politely declines specific stock tips and never asks for passwords or account numbers

## Tech Stack
Python, Streamlit, Gemini API (function calling), ChromaDB (RAG)

## Run Locally
```bash
git clone https://github.com/Lahari-HS/fin-chatbot.git
cd fin-chatbot
pip install -r requirements.txt
cp .env.example .env     # add your Gemini API key
streamlit run app.py
```
Opens at http://localhost:8501

## Disclaimer
Educational information only, not personalized financial advice.
