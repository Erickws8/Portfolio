# impotação das bibliotecas
import string
import random as rd
from PyQt6 import uic, QtWidgets
import pyperclip

# Declaração das variaveis
senhaFinal = ''

# Declaração das funções

def gerarSenha():
    global senhaFinal
    sbTamSenha = gerador_senha.sbTamSenha.value()
    chbLetra = gerador_senha.chbLetra.isChecked()
    chbnum = gerador_senha.chbNum.isChecked()
    chbesp = gerador_senha.chbEsp.isChecked()
    lblSenha = gerador_senha.lblSenha.text()
    
    letras = list(string.ascii_letters)
    num = list(string.digits)
    especial = list(string.punctuation)
    caracteres = []
    caracteres.extend(letras)
    caracteres.extend(num)
    caracteres.extend(especial)
    senha = []

    if chbLetra and chbnum and chbesp:
        for cont in range(sbTamSenha):
            senha.append(rd.choice(caracteres))
        gerador_senha.lblSenha.setText(''.join(senha))   
        senhaFinal = (''.join(senha))

    elif chbLetra and chbnum:
        for item in especial:
            caracteres.remove(item)
        for cont in range(sbTamSenha):
            senha.append(rd.choice(caracteres))
        gerador_senha.lblSenha.setText(''.join(senha))
        senhaFinal = (''.join(senha))

    elif chbLetra and chbesp:
        for item in num:
            caracteres.remove(item)
        for cont in range(sbTamSenha):
            senha.append(rd.choice(caracteres))
        gerador_senha.lblSenha.setText(''.join(senha))
        senhaFinal = (''.join(senha))

    elif chbnum and chbesp:
        for item in letras:
            caracteres.remove(item)
        for cont in range(sbTamSenha):
            senha.append(rd.choice(caracteres))
        gerador_senha.lblSenha.setText(''.join(senha))
        senhaFinal = (''.join(senha))

    elif chbnum:
        for cont in range(sbTamSenha):
            senha.append(rd.choice(num))
        gerador_senha.lblSenha.setText(''.join(senha))
        senhaFinal = (''.join(senha))

    elif chbesp:
        for cont in range(sbTamSenha):
            senha.append(rd.choice(especial))
        gerador_senha.lblSenha.setText(''.join(senha))
        senhaFinal = (''.join(senha))

    elif chbLetra:
        for cont in range(sbTamSenha):
            senha.append(rd.choice(letras))
        gerador_senha.lblSenha.setText(''.join(senha))
        senhaFinal = (''.join(senha))

def copiar():
    pyperclip.copy(senhaFinal)


# Programa principal
app = QtWidgets.QApplication([])
gerador_senha = uic.loadUi('gerador_de_senha_GUI.ui')

gerador_senha.btnCopiar.clicked.connect(copiar)
gerador_senha.btnGerar.clicked.connect(gerarSenha)
gerador_senha.show()
app.exec()