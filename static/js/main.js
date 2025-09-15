// Espera o documento carregar completamente
document.addEventListener('DOMContentLoaded', function() {
    // Procura pelo campo de input com o id 'placa-input'
    const placaInput = document.getElementById('placa-input');

    // Se o campo existir na página...
    if (placaInput) {
        // Adiciona um "ouvinte" que dispara toda vez que o usuário digita algo
        placaInput.addEventListener('input', function(event) {
            // Pega o valor atual do campo, converte para maiúsculas e o define de volta no campo
            event.target.value = event.target.value.toUpperCase();
        });
    }
});