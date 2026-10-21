"""Allowlist de eventos operacionais; nunca formatar erros de bibliotecas/payloads."""
import logging

class SafeFilter(logging.Filter):
    def filter(self,record):
        return record.name=='automation' and record.msg in ('run=%s state=%s','api status=%s duration_ms=%s')
