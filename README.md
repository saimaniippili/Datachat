# DataChat: Conversational Data Analysis with Ollama

DataChat is an interactive web application that lets you analyze and explore your datasets using natural language. Simply upload your CSV or Excel file, and start asking questions about your data in plain English. DataChat leverages the power of Ollama for language understanding and LangChain for seamless integration with data analysis tools.

[![Ollama](https://img.shields.io/badge/Ollama-gemma%3A2b-blueviolet)](https://ollama.ai/)
[![LangChain](https://img.shields.io/badge/LangChain-latest-blue)](https://python.langchain.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📸 Application Interface

<img width="1623" height="1012" alt="Screenshot 2026-06-03 192424" src="https://github.com/user-attachments/assets/e8953ebb-3be0-4289-92f1-34c9685d56b4" />


## ✨ Features

*   **Intuitive Chat Interface:** Ask questions about your data in a conversational manner.
*   **Support for CSV and Excel Files:** Easily upload your data from common file formats.
*   **Powerful Data Analysis:** Get answers to questions about trends, statistics, distributions, and relationships within your data.
*   **Seamless Integration:** Leverages LangChain to connect Ollama with data analysis tools like Pandas.

## 💻 System Requirements

To run this project smoothly (especially since it relies on running local Large Language Models), your system should meet the following requirements:

*   **Processor (CPU):** A modern multi-core processor (Intel Core i5/Ryzen 5 or better). An Apple Silicon (M1/M2/M3) Mac or a dedicated NVIDIA GPU is highly recommended for faster inference speeds.
*   **RAM:** 
    *   **Minimum:** 8 GB RAM (sufficient for smaller 2B models).
    *   **Recommended:** 16 GB to 32 GB RAM (necessary for smoothly running 8B parameter models like `llama3:8b` alongside pandas operations).
*   **Storage:** At least 10-15 GB of free space for downloading the Ollama models and Python dependencies.

## 🧠 Supported Models

DataChat supports various models via Ollama. You can select them directly from the UI dropdown:

*   <span style="color: #ff5722; font-weight: bold;">llama3:8b</span> - Excellent for reasoning and complex data analysis (default).
*   <span style="color: #9c27b0; font-weight: bold;">gemma:2b</span> - Very lightweight and fast.
*   <span style="color: #4caf50; font-weight: bold;">mistral:latest</span> - A strong alternative to Llama 3 for data tasks.
*   <span style="color: #2196f3; font-weight: bold;">gemma2:2b</span> - Google's updated lightweight model.

## 🚀 Getting Started

### 1. Prerequisites
*   **Python 3.9+**
*   **Ollama** installed and running (download from [https://ollama.ai/](https://ollama.ai/))

### 2. Pull Required Models
Open your terminal and pull the models you want to use:
```bash
ollama pull llama3:8b
```

### 3. Installation

```bash
git clone https://github.com/saimaniippili/Datachat.git
cd Datachat
pip install -r requirements.txt
```

### 4. Running the App

```bash
python src/main.py
```
*This will start the local server and automatically open the DataChat UI in your web browser at `http://127.0.0.1:8000`.*

## 💡 Usage

1.  **Upload Data:** Drag and drop or click to choose your CSV or Excel file on the left sidebar.
2.  **Start Chatting:** Type your questions about the data in the chat input box at the bottom.
3.  **Get Answers:** DataChat will process your question and display the answer, complete with any generated charts!

## 📊 Examples

*   "What is the average age of customers?"
*   "How many sales were made in each region?"
*   "Which product category has the highest revenue?"
*   "Show me a histogram of customer ages."

## ⚙️ Customization

*   **LLM:** Experiment with different Ollama models for improved performance.
*   **Data Analysis Tools:** Extend DataChat by adding custom LangChain tools to integrate with other analysis libraries or APIs.

## 📄 License
This project is licensed under the Apache 2.0 License.
