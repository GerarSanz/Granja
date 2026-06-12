# Importar todos los modelos para que Alembic los detecte
from models.usuario import Usuario
from models.lote import Lote, Parcela, AsignacionToro
from models.animal import Animal
from models.reproduccion import Reproduccion
from models.sanidad import Tratamiento, PlanVacunal
from models.alimentacion import Alimento, RacionTipo, StockMovimiento, CompraAlimento
from models.economia import Venta, Gasto
from models.alerta import Alerta
