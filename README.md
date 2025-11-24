# 🚀 Flux Backend

A FastAPI-based backend service for Flux, built with async PostgreSQL support and Pydantic v1 for data validation.

---

## 📦 Requirements

- **Python**: 3.11.9  
  ⚠️ Python 3.14 is not supported due to incompatibilities with `asyncpg` and `pydantic-core`.
- **pip**: ≥ 25.2
- **PostgreSQL**: (for asyncpg connection)
- **Optional**: Rust toolchain (only needed if building certain packages from source)

---

## 🛠️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Hou-dini/flux_backend
cd flux_backend

python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Running the app
uvicorn app.main:app --reload

# Reporducibility notes
- This project uses pydantic==1.10.13 to avoid Rust build issues and Python 3.14 incompatibilities.
- If you encounter build errors with asyncpg or pydantic-core, ensure you're using Python 3.11.9.
