# Medical Telegram Warehouse

This project processes raw Telegram data, warehouses it using dbt, and provides an analytical API via FastAPI.

## Features

- Data ingestion from Telegram

- Data transformation with dbt

- RESTful API for analytics

## Setup

1. Clone the repository

2. Create a virtual environment: `python -m venv venv`

3. Activate it: `venv\Scripts\activate` (Windows)

4. Install dependencies: `pip install -r requirements.txt`

5. Set up environment variables in `.env`

6. Run with Docker: `docker-compose up --build`

7. Or run locally: `uvicorn api.main:app --reload`

## Usage

- API docs at http://localhost:8000/docs

- dbt models in medical_warehouse/

## Contributing

Follow standard practices.