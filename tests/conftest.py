# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
import os
import tempfile

import pytest

# La base de pruebas va a una carpeta temporal, nunca a la real
os.environ["PRESUPUESTOS_DATA_DIR"] = tempfile.mkdtemp(prefix="presupuestos_test_")


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.database import Base, engine
    from app.main import app

    with TestClient(app) as c:
        yield c
    # limpiar datos entre tests, manteniendo el esquema
    with engine.begin() as conn:
        for t in reversed(Base.metadata.sorted_tables):
            conn.execute(t.delete())
