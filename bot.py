from telegram.ext import Application, MessageHandler, filters, CommandHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import os
import json
import io
import matplotlib.pyplot as plt

load_dotenv()

# Setup Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Get the credentials JSON from the environment variable

credentials_json = os.getenv("GOOGLE_CREDENTIALS")

if credentials_json:
    try:
        parsed = json.loads(credentials_json)
    except json.JSONDecodeError as e:
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
    if any(word in item for word in ["restaurante", "café", "hambúrguer", "mcdonald", "pizza", "burger", "sushi", "jantar", "snack"]):
        return "Alimentação fora de casa"
    
    # Supermercado
    if any(word in item for word in ["mercado", "supermercado", "pingo doce", "continente", "minipreço", "lidl", "intermarché", "auchan", "aldi"]):
        return "Supermercado"

    # Saúde
    if any(word in item for word in ["farmácia", "medicamento", "médico", "dentista", "óculos", "consulta"]):
        return "Saúde"

    # Lazer
    if any(word in item for word in ["netflix", "spotify", "cinema", "jogo", "livro", "bilhete", "evento", "lazer", "hotel", "airbnb"]):
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
    
    if any(word in item for word in ["tabaco", "cigarro", "cigarros"]):
        return "Tabaco"

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
# Handle the "resumo <month>" command
async def resumo(update, context):
    if len(context.args) < 1:
        # No month specified, summarize all months
        month_name = None
    else:
        month_name = context.args[0].lower()
    
    # Map month name to month number
    month_map = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6,
        'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    
    if month_name and month_name not in month_map:
        await update.message.reply_text("❌ Mês inválido. Use um mês válido (ex: maio).")
        return
    
    # Fetch the sheet data
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    
    # Ensure the 'Data' column is in datetime format
    df['Data'] = pd.to_datetime(df['Data'])
    
    if month_name:
        # Filter by the given month
        month_num = month_map[month_name]
        df['Month'] = df['Data'].dt.month
        df_filtered = df[df['Month'] == month_num]
        
        if df_filtered.empty:
            await update.message.reply_text(f"❌ Não há despesas registradas para o mês de {month_name}.")
            return
        
        # Summarize expenses by category
        summary = df_filtered.groupby('Categoria')['Montante'].sum().reset_index()

        # Prepare the response message
        response = f"Resumo de despesas para o mês de {month_name}:\n"
        for _, row in summary.iterrows():
            response += f"{row['Categoria']}: {row['Montante']:.2f}€\n"

        # Calculate savings for the specified month
        total_expenses = df_filtered['Montante'].sum()
        savings = 1500 - total_expenses
        response += f"\n📉 Total de despesas: {total_expenses:.2f}€"
        response += f"\n🐷 Poupança: {savings:.2f}€"
        await update.message.reply_text(response)
    else:
        # Summarize expenses for all months
        df['Month'] = df['Data'].dt.month
        summary_all_months = df.groupby(['Month', 'Categoria'])['Montante'].sum().reset_index()

        # Prepare the response message for all months
        response = "Resumo de despesas por mês:\n"
        for month_num in range(1, 13):
            month_name = list(month_map.keys())[month_num - 1]
            df_month = summary_all_months[summary_all_months['Month'] == month_num]
            
            if df_month.empty:
                continue  # Skip empty months
            
            response += f"\nMês de {month_name}:\n"
            for _, row in df_month.iterrows():
                response += f"{row['Categoria']}: {row['Montante']:.2f}€\n"

            # Calculate savings for the month
            total_expenses = df_month['Montante'].sum()
            savings = 1500 - total_expenses
            response += f"📉 Total de despesas: {total_expenses:.2f}€\n"
            response += f"🐷 Poupança: {savings:.2f}€\n"

        await update.message.reply_text(response)



# Handle the "despesas <month>" command
async def despesas(update, context):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Por favor, forneça o mês (ex: despesas maio).")
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
    
    # Prepare the response message
    response = f"Despesas para o mês de {month_name}:\n\n"
    response += "Item | Montante | Categoria | Descrição\n"
    response += "-------------------------------------------\n"
    for _, row in df_filtered.iterrows():
        response += f"{row['Item']} | {row['Montante']:.2f}€ | {row['Categoria']} | {row['Descrição']}\n"
    
    await update.message.reply_text(response)

# Function to generate and send a chart
async def gerar_grafico(update, context):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Por favor, forneça o mês (ex: grafico maio).")
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

    # Prepare data for the pie chart
    categories = summary['Categoria'].tolist()
    amounts = summary['Montante'].tolist()

    # Create a pie chart
    fig, ax = plt.subplots()
    ax.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    # Save the plot in a memory buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Send the plot to the user
    await update.message.reply_photo(buf, caption=f"Gráfico de despesas para o mês de {month_name.capitalize()}")

    # Close the plot to free memory
    plt.close(fig)


# Start bot
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    # Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("resumo", resumo))
    app.add_handler(CommandHandler("despesas", despesas))
    app.add_handler(CommandHandler("grafico", gerar_grafico))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()