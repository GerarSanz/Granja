// GranjaManager — utilidades JS globales

document.addEventListener('DOMContentLoaded', function () {

    // Rellenar automáticamente inputs de fecha vacíos con hoy
    const hoy = new Date().toISOString().split('T')[0];
    document.querySelectorAll('input[type="date"]:not([value])').forEach(function (el) {
        if (!el.value && !el.closest('form[method="get"]')) {
            el.value = hoy;
        }
    });

    // Mayúsculas automáticas en campos de crotal
    document.querySelectorAll('input.text-uppercase').forEach(function (el) {
        el.addEventListener('input', function () {
            const pos = this.selectionStart;
            this.value = this.value.toUpperCase();
            this.setSelectionRange(pos, pos);
        });
    });

    // Confirmar antes de dar de baja
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm(form.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // Cerrar alertas flash después de 5 segundos
    document.querySelectorAll('.alert-dismissible.auto-dismiss').forEach(function (el) {
        setTimeout(function () {
            const btn = el.querySelector('.btn-close');
            if (btn) btn.click();
        }, 5000);
    });

});
