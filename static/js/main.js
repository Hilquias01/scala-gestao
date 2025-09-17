document.addEventListener('DOMContentLoaded', function () {
    const placaInput = document.getElementById('placa-input');
    if (placaInput) {
        const placaMask = IMask(placaInput, {
            mask: [
                {
                    mask: 'AAA-0000',
                    definitions: { 'A': /[A-Z]/ } // Define 'A' como qualquer letra maiúscula
                },
                {
                    mask: 'AAA-0A00',
                    definitions: { 'A': /[A-Z]/ } // Define 'A' como qualquer letra maiúscula
                }
            ],
            prepare: function (str) {
                return str.toUpperCase(); // Sempre converte para maiúsculo
            },
        });
    }

    const moneyInputs = document.querySelectorAll('.money-mask');
    moneyInputs.forEach(function(input) {
        const moneyMask = IMask(input, {
            mask: 'R$ num',
            blocks: {
                num: {
                    mask: Number,
                    scale: 2,
                    thousandsSeparator: '.',
                    padFractionalZeros: true,
                    radix: ',',
                    mapToRadix: ['.']
                }
            }
        });
    });
});