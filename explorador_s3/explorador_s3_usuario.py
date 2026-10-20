"""Explorador S3 para suporte. pip install boto3 pillow
Credenciais: variáveis no início deste arquivo; como alternativa, perfil AWS.
ATENÇÃO: chaves embutidas podem ser extraídas do script ou executável.
"""
import os
import sys
import queue
import threading
import configparser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError, ProfileNotFound

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

BUCKET = 'backup-sig2000'
RAIZ = 'firebird-backup/'
REGIAO = 'us-east-1'
# PREENCHA ESTAS VARIÁVEIS PARA CONECTAR AUTOMATICAMENTE.
# Para credenciais permanentes, AWS_SESSION_TOKEN deve permanecer vazio.
# Para credenciais temporárias, preencha as três variáveis.
AWS_ACCESS_KEY_ID = 'access key'
AWS_SECRET_ACCESS_KEY = 'access key secret'
AWS_SESSION_TOKEN = ''

# Alternativa quando as variáveis acima estiverem vazias.
PERFIL_PADRAO = 'sig2000-suporte'
AZUL = '#142D4E'
FUNDO = '#F1F5F9'


def pasta_app():
    return Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent


def config_app():
    cfg = configparser.ConfigParser(interpolation=None)
    arquivo = pasta_app() / 'config.ini'
    if arquivo.exists():
        cfg.read(arquivo, encoding='utf-8-sig')
    return cfg


def tamanho_legivel(n):
    n = float(n)
    for unidade in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unidade == 'TB':
            return f'{n:.1f} {unidade}'
        n /= 1024


class ExploradorSuporte(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Explorador S3')
        self.geometry('1080x700')
        self.minsize(600, 430)
        self.configure(bg=FUNDO)
        self.fila = queue.Queue()
        self.cliente = None
        self.prefixo = RAIZ
        self.itens_todos = []
        self.visiveis = {}
        self.ocupado = False
        self.config = config_app()
        self._definir_icone_janela()
        self._interface()
        self.after(100, self._eventos)
        self.after(250, self.conectar)

    def _interface(self):
        cab = tk.Frame(self, bg=AZUL, padx=14, pady=12)
        cab.pack(fill='x')
        self.logo_quadro = tk.Frame(cab, bg='white', width=112, height=92)
        self.logo_quadro.pack(side='left', padx=(0, 14))
        self.logo_quadro.pack_propagate(False)
        self.logo = tk.Label(self.logo_quadro, text='SIG2000', bg='white', fg=AZUL,
                             font=('Segoe UI', 12, 'bold'), anchor='center')
        self.logo.pack(fill='both', expand=True)
        self._carregar_logo()
        bloco = tk.Frame(cab, bg=AZUL)
        bloco.pack(side='left', fill='both', expand=True)
        tk.Label(bloco, text='EXPLORADOR S3', bg=AZUL,
                 fg='white', font=('Segoe UI', 15, 'bold'), anchor='w').pack(fill='x')
        tk.Label(bloco, text=f'BACKUP FIREBIRD', bg=AZUL,
                 fg='#D5E3F3', font=('Segoe UI', 9), anchor='w').pack(fill='x')

        barra = tk.Frame(self, bg=FUNDO, padx=12, pady=10)
        barra.pack(fill='x')
        self.voltar_btn = tk.Button(barra, text='↑ Voltar', command=self.voltar)
        self.voltar_btn.pack(side='left', padx=(0, 6))
        self.atualizar_btn = tk.Button(barra, text='↻ Atualizar', command=self.atualizar)
        self.atualizar_btn.pack(side='left', padx=(0, 6))
        self.conectar_btn = tk.Button(barra, text='Reconectar', command=self.conectar)
        self.conectar_btn.pack(side='left')
        self.estado_var = tk.StringVar(value='Aguardando conexão...')
        tk.Label(barra, textvariable=self.estado_var, bg=FUNDO, fg=AZUL,
                 font=('Segoe UI', 9)).pack(side='right')

        pesquisa = tk.Frame(self, bg=FUNDO, padx=12)
        pesquisa.pack(fill='x')
        tk.Label(pesquisa, text='Buscar nesta pasta:', bg=FUNDO,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.busca_var = tk.StringVar()
        self.busca_var.trace_add('write', lambda *_: self.filtrar())
        self.busca = ttk.Entry(pesquisa, textvariable=self.busca_var, font=('Segoe UI', 11))
        self.busca.pack(side='left', fill='x', expand=True, pady=(4, 8))
        ttk.Button(pesquisa, text='Limpar', command=lambda: self.busca_var.set('')).pack(
            side='left', padx=(8, 0), pady=(4, 8))

        tabela = tk.Frame(self, bg='white')
        tabela.pack(fill='both', expand=True, padx=12, pady=(6, 8))
        self.arvore = ttk.Treeview(tabela, columns=('tipo', 'tamanho', 'data'),
                                   show='tree headings', selectmode='extended')
        for col, titulo, largura in (('#0', 'Nome', 400), ('tipo', 'Tipo', 85),
                                     ('tamanho', 'Tamanho', 105), ('data', 'Modificado em', 160)):
            self.arvore.heading(col, text=titulo)
            self.arvore.column(col, width=largura, minwidth=80, stretch=(col == '#0'))
        tabela.grid_rowconfigure(0, weight=1)
        tabela.grid_columnconfigure(0, weight=1)
        self.arvore.grid(row=0, column=0, sticky='nsew')
        sy = ttk.Scrollbar(tabela, orient='vertical', command=self.arvore.yview)
        sx = ttk.Scrollbar(tabela, orient='horizontal', command=self.arvore.xview)
        self.arvore.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.arvore.bind('<Double-1>', self.abrir_pasta)

        rodape = tk.Frame(self, bg='white', padx=12, pady=10)
        rodape.pack(fill='x', padx=12, pady=(0, 10))
        tk.Label(rodape, text='Destino dos downloads:', bg='white').grid(
            row=0, column=0, columnspan=3, sticky='w')
        self.destino_var = tk.StringVar(value=str(Path.home() / 'Downloads'))
        ttk.Entry(rodape, textvariable=self.destino_var).grid(
            row=1, column=0, sticky='ew', pady=(5, 8))
        ttk.Button(rodape, text='Escolher pasta', command=self.escolher_pasta).grid(
            row=1, column=1, padx=(8, 0), pady=(5, 8))
        self.baixar_btn = tk.Button(rodape, text='↓ BAIXAR SELECIONADOS',
                                   command=self.baixar, bg='#15803D', fg='white',
                                   relief='flat', padx=12, pady=7)
        self.baixar_btn.grid(row=1, column=2, padx=(8, 0), pady=(5, 8))
        rodape.columnconfigure(0, weight=1)
        self.progresso = ttk.Progressbar(rodape, maximum=100)
        self.progresso.grid(row=2, column=0, columnspan=3, sticky='ew')
        self.status_var = tk.StringVar(value='A conexão será iniciada automaticamente.')
        tk.Label(rodape, textvariable=self.status_var, bg='white',
                 anchor='w', fg='#64748B').grid(row=3, column=0, columnspan=3, sticky='ew', pady=(5, 0))
        self._ocupado(False)

    def _definir_icone_janela(self):
        """Usa logo.ico ao lado do .py ou do .exe como ícone da janela."""
        caminho = pasta_app() / 'logo.ico'
        if not caminho.is_file():
            return
        try:
            if sys.platform.startswith('win'):
                self.iconbitmap(str(caminho))
            elif Image is not None:
                with Image.open(caminho) as imagem:
                    self._icone_ref = ImageTk.PhotoImage(imagem.convert('RGBA'))
                self.iconphoto(True, self._icone_ref)
        except (OSError, ValueError, tk.TclError):
            pass

    def _carregar_logo(self):
        """Carrega logo.ico ao lado do .py/.exe na melhor resolução disponível.

        Ajusta a imagem proporcionalmente à área branca de 112x92 pixels,
        sem deformar nem ampliar imagens pequenas além da resolução original.
        """
        caminho = pasta_app() / 'logo.ico'
        if not caminho.is_file():
            return
        if Image is None or ImageTk is None:
            self.logo.configure(text='Instale Pillow\npara ver a logo')
            return
        try:
            with Image.open(caminho) as ico:
                # Um .ico costuma conter vários tamanhos (16, 32, 48, 256).
                # O Pillow pode abrir por padrão uma versão pequena; priorizamos
                # a maior para evitar uma logo pixelada no cabeçalho.
                tamanhos = ico.info.get('sizes', set())
                if tamanhos:
                    melhor = max(tamanhos, key=lambda t: t[0] * t[1])
                    try:
                        ico.size = melhor
                    except (AttributeError, ValueError):
                        pass
                imagem = ico.convert('RGBA')
                imagem.thumbnail((100, 80), Image.Resampling.LANCZOS)
                self._logo_ref = ImageTk.PhotoImage(imagem)
            self.logo.configure(image=self._logo_ref, text='', compound='center')
        except (OSError, ValueError, tk.TclError) as erro:
            self.logo.configure(text='SIG2000')
            print(f'Não foi possível carregar logo.ico: {erro}')

    def _ocupado(self, valor):
        self.ocupado = valor
        for botao in (self.voltar_btn, self.atualizar_btn, self.conectar_btn, self.baixar_btn):
            botao.configure(state='disabled' if valor else 'normal')

    def _executar(self, func, *args):
        threading.Thread(target=func, args=args, daemon=True).start()

    def conectar(self):
        if self.ocupado:
            return
        self._ocupado(True)
        self.estado_var.set('Conectando...')
        self.status_var.set('Conectando à AWS e abrindo firebird-backup/...')
        self._executar(self._conectar_worker)

    def _conectar_worker(self):
        try:
            access = AWS_ACCESS_KEY_ID.strip()
            secret = AWS_SECRET_ACCESS_KEY.strip()
            token = AWS_SESSION_TOKEN.strip()
            if access or secret or token:
                if not access or not secret:
                    raise ValueError('Informe AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY no script. '
                                     'AWS_SESSION_TOKEN é opcional para credenciais permanentes.')
                sessao = boto3.Session(
                    aws_access_key_id=access,
                    aws_secret_access_key=secret,
                    aws_session_token=token or None,
                    region_name=REGIAO,
                )
            else:
                perfil = self.config.get('AWS', 'profile', fallback=PERFIL_PADRAO).strip()
                try:
                    sessao = (boto3.Session(profile_name=perfil, region_name=REGIAO)
                              if perfil else boto3.Session(region_name=REGIAO))
                    sessao.get_credentials()
                except ProfileNotFound:
                    if self.config.has_option('AWS', 'profile'):
                        raise
                    sessao = boto3.Session(region_name=REGIAO)
            cliente = sessao.client('s3', config=Config(connect_timeout=10, read_timeout=60,
                                                         retries={'max_attempts': 3}))
            self._listar_worker(cliente, RAIZ)
        except Exception as erro:
            self.fila.put(('erro', str(erro)))

    def _listar_worker(self, cliente, prefixo):
        try:
            itens = []
            paginas = cliente.get_paginator('list_objects_v2').paginate(
                Bucket=BUCKET, Prefix=prefixo, Delimiter='/')
            for pagina in paginas:
                for pasta in pagina.get('CommonPrefixes', []):
                    chave = pasta['Prefix']
                    itens.append({'tipo': 'Pasta', 'nome': chave[len(prefixo):].rstrip('/'), 'key': chave})
                for obj in pagina.get('Contents', []):
                    chave = obj['Key']
                    if chave == prefixo or chave.endswith('/'):
                        continue
                    data = obj.get('LastModified')
                    itens.append({'tipo': 'Arquivo', 'nome': chave[len(prefixo):], 'key': chave,
                                  'tamanho': obj.get('Size', 0),
                                  'data': data.strftime('%d/%m/%Y %H:%M') if data else ''})
            itens.sort(key=lambda x: (x['tipo'] != 'Pasta', x['nome'].casefold()))
            self.fila.put(('lista', cliente, prefixo, itens))
        except Exception as erro:
            self.fila.put(('erro', str(erro)))

    def filtrar(self):
        termo = self.busca_var.get().casefold().strip()
        self.arvore.delete(*self.arvore.get_children())
        self.visiveis.clear()
        for item in self.itens_todos:
            if termo and termo not in item['nome'].casefold():
                continue
            ident = self.arvore.insert('', 'end', text=('📁 ' if item['tipo'] == 'Pasta' else '📄 ') + item['nome'],
                                      values=(item['tipo'], tamanho_legivel(item.get('tamanho', 0))
                                              if item['tipo'] == 'Arquivo' else '', item.get('data', '')))
            self.visiveis[ident] = item
        self.status_var.set(f'{len(self.visiveis)} exibido(s) de {len(self.itens_todos)} item(ns).')

    def navegar(self, prefixo):
        if self.ocupado or not self.cliente:
            return
        if not prefixo.startswith(RAIZ):
            return
        self._ocupado(True)
        self.status_var.set('Carregando pasta...')
        self._executar(self._listar_worker, self.cliente, prefixo)

    def voltar(self):
        if self.prefixo == RAIZ:
            return
        partes = self.prefixo.rstrip('/').split('/')
        anterior = '/'.join(partes[:-1]) + '/'
        self.navegar(anterior if anterior.startswith(RAIZ) else RAIZ)

    def atualizar(self):
        if self.cliente:
            self.navegar(self.prefixo)
        else:
            self.conectar()

    def abrir_pasta(self, _evento=None):
        selecao = self.arvore.selection()
        if len(selecao) == 1:
            item = self.visiveis.get(selecao[0])
            if item and item['tipo'] == 'Pasta':
                self.navegar(item['key'])

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.destino_var.get())
        if pasta:
            self.destino_var.set(pasta)

    @staticmethod
    def _caminho_seguro(nome):
        partes = nome.split('/')
        if not nome or nome.startswith('/') or any(
                not parte or parte in ('.', '..') or ':' in parte or '\\' in parte or
                parte.rstrip(' .') != parte for parte in partes):
            raise ValueError(f'Caminho S3 inválido para download: {nome}')
        return Path(*partes)

    def baixar(self):
        if self.ocupado or not self.cliente:
            return
        selecionados = [self.visiveis[i].copy() for i in self.arvore.selection() if i in self.visiveis]
        if not selecionados:
            messagebox.showinfo('Seleção', 'Selecione um ou mais arquivos ou pastas.')
            return
        destino = Path(self.destino_var.get().strip()).expanduser()
        if not str(self.destino_var.get()).strip():
            messagebox.showwarning('Destino', 'Selecione uma pasta de destino.')
            return
        if not messagebox.askyesno('Confirmar download',
                'Baixar os itens selecionados? Arquivos existentes serão substituídos.'):
            return
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            messagebox.showerror('Destino', str(erro))
            return
        self.progresso['value'] = 0
        self._ocupado(True)
        self._executar(self._baixar_worker, selecionados, destino)

    def _baixar_worker(self, selecionados, destino):
        try:
            tarefas = {}
            for item in selecionados:
                if item['tipo'] == 'Arquivo':
                    tarefas[item['key']] = (item['nome'], item.get('tamanho', 0))
                else:
                    for pagina in self.cliente.get_paginator('list_objects_v2').paginate(
                            Bucket=BUCKET, Prefix=item['key']):
                        for obj in pagina.get('Contents', []):
                            chave = obj['Key']
                            if not chave.endswith('/'):
                                nome = item['nome'] + '/' + chave[len(item['key']):]
                                tarefas[chave] = (nome, obj.get('Size', 0))
            arquivos = [(key, destino / self._caminho_seguro(nome), nome, tamanho)
                        for key, (nome, tamanho) in tarefas.items()]
            total = sum(a[3] for a in arquivos)
            completo = 0
            for indice, (key, alvo, nome, tamanho) in enumerate(arquivos, 1):
                alvo.parent.mkdir(parents=True, exist_ok=True)
                temp = alvo.with_name(alvo.name + '.part')
                atual = 0
                def progresso(pedaco):
                    nonlocal atual
                    atual += pedaco
                    percent = (completo + atual) / total * 100 if total else (indice-1)/len(arquivos)*100
                    self.fila.put(('progresso', min(100, percent), f'Baixando {indice}/{len(arquivos)}: {nome}'))
                try:
                    self.cliente.download_file(BUCKET, key, str(temp), Callback=progresso)
                    os.replace(temp, alvo)
                except Exception:
                    temp.unlink(missing_ok=True)
                    raise
                completo += tamanho
                self.fila.put(('progresso', completo / total * 100 if total else indice/len(arquivos)*100,
                               f'Concluído {indice}/{len(arquivos)}: {nome}'))
            self.fila.put(('concluido', len(arquivos)))
        except Exception as erro:
            self.fila.put(('erro', str(erro)))

    def _eventos(self):
        try:
            while True:
                ev = self.fila.get_nowait()
                if ev[0] == 'lista':
                    _, self.cliente, self.prefixo, self.itens_todos = ev
                    self.busca_var.set('')
                    self.filtrar()
                    self.estado_var.set('● Conectado')
                    self._ocupado(False)
                elif ev[0] == 'progresso':
                    self.progresso['value'] = ev[1]
                    self.status_var.set(ev[2])
                elif ev[0] == 'concluido':
                    self._ocupado(False)
                    self.progresso['value'] = 100
                    self.status_var.set(f'Download concluído: {ev[1]} arquivo(s).')
                    messagebox.showinfo('Download concluído', f'{ev[1]} arquivo(s) baixado(s).')
                elif ev[0] == 'erro':
                    self._ocupado(False)
                    self.estado_var.set('● Falha na operação')
                    self.status_var.set('Erro. Verifique a conexão, credenciais e permissões.')
                    messagebox.showerror('Erro AWS', ev[1])
        except queue.Empty:
            pass
        self.after(100, self._eventos)


if __name__ == '__main__':
    ExploradorSuporte().mainloop()
