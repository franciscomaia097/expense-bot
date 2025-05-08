from telegram.ext import Application, MessageHandler, filters, CommandHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import os
import json
load_dotenv()

# Setup Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Get the credentials JSON from the environment variable
credentials_json = os.getenv("GOOGLE_CREDENTIALS")

import os
import json

credentials_json = os.getenv("GOOGLE_CREDENTIALS")

if credentials_json:
    try:
        parsed = json.loads(credentials_json)
        print("Loaded JSON successfully.")
    except json.JSONDecodeError as e:
        print(f"JSON error: {e}")
        print(f"Raw env: {credentials_json[:100]}...")  # Mostra só o início para debugging
        exit(1)

    creds = ServiceAccountCredentials.from_json_keyfile_dict(parsed, scope)
else:
    print("Google credentials not found!")
    exit(1)


# Setup Google Sheets
client = gspread.authorize(creds)
sheet = client.open("Despesas").sheet1

def categorize(item):
    item = item.lower()

    # Transporte
    if any(word in item for word in ["gasóleo", "combustível", "gasolina", "transporte", "cp", "metro", "vistoria", "selo", "seguro"]):
        return "Carro"
    
    # Mobilidade (apps)
    if any(word in item for word in ["uber", "táxi", "bolt", "cabify"]):
        return "Mobilidade"

    # Alimentação fora de casa
    if any(word in item for word in ["restaurante", "café", "hambúrguer", "mcdonald", "pizza", "burger", "sushi", "pastelaria", "snack"]):
        return "Alimentação fora de casa"
    
    # Supermercado
    if any(word in item for word in ["mercado", "supermercado", "pingo doce", "continente", "minipreço", "lidl", "intermarché", "auchan", "aldi"]):
        return "Supermercado"

    # Saúde
    if any(word in item for word in ["farmácia", "medicamento", "médico", "dentista", "óculos", "consulta"]):
        return "Saúde"

    # Lazer
    if any(word in item for word in ["netflix", "spotify", "cinema", "jogo", "livro", "bilhete", "evento", "lazer"]):
        return "Lazer"
    
    # Casa
    if any(word in item for word in ["renda", "aluguel", "água", "eletricidade", "luz", "gás", "internet", "meo", "vodafone", "nos", "eDP"]):
        return "Casa"

    # Desporto / Saúde física
    if any(word in item for word in ["ginásio", "academia", "fitness", "jiu-jitsu", "kickbox", "suplemento", "creatina"]):
        return "Desporto"

    # Educação
    if any(word in item for word in ["curso", "formação", "aula", "licença", "certificado"]):
        return "Educação"

    if any(word in item for word in ["xtb", "investimento", "banco", "carteira", "carteira de investimentos", "carteira de investimentos", "carteira de investimentos", "carteira de investimentos"]):
        return "Investimentos"

    # Transferências financeiras
    if any(word in item for word in ["mbway", "transferência", "paypal", "wise", "revolut"]):
        return "Transferência / Outros"

    return "Outros"


# Handle incoming messages to add expenses with description
async def handle_message(update, context):
    text = update.message.text.strip()
    if not text:
        return

    try:
        parts = text.rsplit(" - ", 2)  # Split into 3 parts (item, amount, description)
        if len(parts) < 2:
            await update.message.reply_text("❌ Formato inválido. Exemplo: Café - 2.50 - café com amigos")
            return
        
        item = parts[0]
        amount = float(parts[1].replace(",", "."))

        # If description is not provided, use an empty string
        description = parts[2] if len(parts) == 3 else ""

        today = datetime.now().strftime("%Y-%m-%d")
        category = categorize(item)

        # Append to the Google Sheet with description
        sheet.append_row([today, item, amount, category, description])
        await update.message.reply_text(f"✅ Added: {item} - {amount:.2f} € on {today}" + (f" - Description: {description}" if description else ""))
    except Exception as e:
        await update.message.reply_text("❌ Formato inválido. Exemplo: Café - 2.50 - café com amigos")


# Handle the "resumo <month>" command
async def resumo(update, context):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Por favor, forneça o mês (ex: resumo maio).")
        return
    
    month_name = context.args[0].lower()
    
    # Map month name to month number
    month_map = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6,
        'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    if month_name not in month_map:
        await update.message.reply_text("❌ Mês inválido. Use um mês válido (ex: maio).")
        return
    
    month_num = month_map[month_name]
    
    # Fetch the sheet data
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    
    # Ensure the 'Data' column is in datetime format
    df['Data'] = pd.to_datetime(df['Data'])
    
    # Filter by the given month
    df['Month'] = df['Data'].dt.month
    df_filtered = df[df['Month'] == month_num]
    
    # If no data for that month
    if df_filtered.empty:
        await update.message.reply_text(f"❌ Não há despesas registradas para o mês de {month_name}.")
        return
    
    # Summarize expenses by category
    summary = df_filtered.groupby('Categoria')['Montante'].sum().reset_index()

    # Prepare the response message
    response = f"Resumo de despesas para o mês de {month_name}:\n"
    for _, row in summary.iterrows():
        response += f"{row['Categoria']}: {row['Montante']:.2f}€\n"

    await update.message.reply_text(response)


# Start bot
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    # Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("resumo", resumo))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
