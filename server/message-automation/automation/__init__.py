"""Serviço independente; nunca inicializa conexão WhatsApp ao importar."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
