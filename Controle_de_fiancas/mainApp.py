from PyQt6 import uic, QtWidgets



def abremov():
    movimentacao.show()   

app = QtWidgets.QApplication([])
# Declaração de formularios
main = uic.loadUi('main.ui')
movimentacao = uic.loadUi('movimentacao.ui')

# Botões form main
main.btnCadastro.clicked.connect(abremov)

#Botões do form movimentação
main.show()
app.exec()