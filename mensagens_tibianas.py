"""Humor original de Tibia, local e sem repetição durante cada ciclo da sessão."""
import hashlib
import random
import threading

MENSAGENS = (
    'Rashid passa a semana viajando e ainda encontra tempo para negociar. Meu personagem atravessa Thais e já precisa conferir se trouxe a rope.',
    'Abri o loot do Oberon com a confiança de quem já escolheu a cor da montaria nova. Fechei com a experiência de quem sabe guardar expectativas no depot.',
    'O grupo marcou Drume para uma visita rápida. No chat, “rápida” significa que todos concordaram com o horário e cada um entendeu um horário diferente.',
    'O chapéu do Ferumbras é famoso em todo Tibia. O meu equipamento também chama atenção, principalmente quando alguém pergunta por que ainda não troquei.',
    'Um Pirate Ghost já viu muita tempestade e continua por aí. Eu vejo a backpack cheia no meio da hunt e considero aquilo uma emergência marítima.',
    'Entrar em PoH sem olhar o caminho é uma forma criativa de conhecer uma Giant Spider. Ela costuma dispensar a apresentação e ir direto ao assunto.',
    'Os rats de Rookgaard ensinaram uma lição que vale até hoje: antes de planejar grandes aventuras, descubra onde foi parar seu equipamento.',
    'A rope pesa pouco na backpack e muito na consciência quando fica no depot. Nenhum mapa avisa que o verdadeiro buraco era no planejamento.',
    'O cyclops dispensa discursos complicados: olha o aventureiro e já sabe o que quer. Eu abro o Market e preciso de quinze minutos para decidir uma oferta.',
    'O parcel leva coisas de uma cidade para outra sem reclamar da caminhada. Ainda estou esperando alguém lançar essa vocação para jogadores.',
    'Meu depot é uma coleção organizada de coisas que talvez sejam úteis um dia. A parte organizada existe apenas no discurso de apresentação.',
    'Fui ao banco conferir o resultado da hunt. O saldo fez silêncio, mas as potions na backpack tinham uma explicação bastante convincente.',
    'Cap é aquele detalhe que transforma um guerreiro destemido em alguém negociando com um pedaço de ham para abrir espaço na backpack.',
    'Levei comida para uma longa aventura e voltei com mais backpacks do que respostas. A logística do loot merecia uma guild só para ela.',
    'Utani hur resolve a pressa, mas ainda não resolve sair sem conferir o inventário. Agora eu esqueço a mesma coisa e percebo isso mais longe.',
    'Exura é uma palavra pequena com uma responsabilidade enorme. Na dúvida, prefiro que a conversa sobre healing seja longa e a barra de vida também.',
    'Utevo lux ilumina a caverna, mas não explica por que entrei nela com a backpack errada. Algumas sombras são problemas de organização.',
    'A SD estava na hotkey certa. O alvo estava no lugar certo. Só faltava combinar com o meu dedo, que decidiu participar de outra estratégia.',
    'Uma GFB reúne criaturas e opiniões sobre posicionamento. Se o grupo inteiro comentou ao mesmo tempo, talvez fosse hora de revisar o plano.',
    'Mana potion é o tipo de investimento que some enquanto você pensa no lucro. No fim da hunt, a calculadora sempre pede para conversar em particular.',
    'Conferi as health potions antes de sair e me senti muito responsável. Agora só preciso adquirir o hábito igualmente importante de apertar a hotkey.',
    'Minha stamina tem mais planejamento do que minha agenda. Se o resto da vida tivesse uma barrinha colorida, talvez eu respeitasse melhor os horários.',
    'Bless não impede uma decisão ruim, mas combina muito bem com o momento em que você lembra de todas as decisões ruins que poderia ter evitado.',
    'O Amulet of Loss tem um nome sincero. Já a minha desculpa depois de uma aventura mal planejada costuma precisar de bastante edição.',
    'Fui escolher a prey e saí calculando uma hunt inteira. A criatura nem sabe, mas já participou de uma reunião de orçamento e planejamento.',
    'Charm é o prêmio por conhecer uma criatura muito bem. Muito bem mesmo: chega uma hora em que você reconhece a família inteira pelo caminho.',
    'No bestiary, cada criatura conta uma história. Algumas histórias são curtas; outras viram uma convivência tão longa que já mereciam convite para a guild.',
    'O bosstiary registra encontros importantes. A minha memória registra principalmente quem disse que aquela tentativa seria rapidinha.',
    'A reward chest recebe minha visita com toda a minha esperança. Eu saio de lá com um item, uma análise e um discurso sobre pensar no longo prazo.',
    'Tibia Coin tem cotação; a alegria de encontrar a backpack que você achava perdida ainda não. Melhor não dar essa ideia ao Market.',
    'Gold Token parece simples até você decidir gastar. De repente, um clique no inventário vira uma reunião com todos os seus projetos de equipamento.',
    'Silver Token na backpack dá aquela sensação de progresso. A lista de coisas que quero comprar responde com uma sensação ainda maior de orçamento.',
    'Scarlett entrou na lista de bosses do dia. Meu grupo levou experiência, eu levei potions e todos levamos uma opinião sobre quem devia começar.',
    'Marcar Timira com o grupo é fácil. O desafio extra é fazer todo mundo chegar preparado e descobrir se aquele “já estou indo” era literal.',
    'Urmahlullu parece ter muita coisa para dizer. Eu também, mas prefiro guardar o comentário para quando a situação estiver um pouco mais confortável.',
    'Thais tem gente negociando com tanta convicção que até um pedaço de ham parece investimento. O verdadeiro rare é encontrar duas ofertas com o mesmo preço.',
    'Disse “hi” ao NPC em Carlin e esperei que ele adivinhasse o resto. Nem o oráculo merece trabalhar com esse nível de mistério.',
    'O barco estava em Venore, o grupo combinou Edron e alguém respondeu “sim”. Ficou tudo esclarecido, exceto em qual cidade ele pretendia desembarcar.',
    'Darashia tem areia e aventureiros cheios de histórias. O dragon também tem uma história para contar, mas prefere uma apresentação mais calorosa.',
    'Em Ankrahmun, perguntei há quanto tempo aquela história começou. Pela quantidade de detalhes, concluí que o NPC estava esperando alguém perguntar há séculos.',
    'Fui pescar em Port Hope para fugir da correria. O worm participou da atividade sem opinião; eu participei olhando a água como se fosse negociar com o peixe.',
    '“Conheço Banuta”, disse o guia do grupo. Dez minutos depois, descobrimos que ele conhecia a aparência e ainda estava negociando com a geografia.',
    'Kazordoon valoriza um bom caminho entre as montanhas. Meu grupo valoriza o amigo que sabe explicar esse caminho sem usar “vira ali naquela parte”.',
    'Em Ab’Dendriel, as árvores tornam qualquer conversa mais elegante. Até o velho “cadê você?” ganha cara de expedição diplomática entre os andares.',
    'Liberty Bay combina com histórias de piratas. A nossa começou com coragem, seguiu com uma dúvida sobre o barco e terminou com todos perguntando o destino.',
    'Em Edron, um rotworm não pede currículo nem pergunta seu level. Vê um aventureiro chegando e já começa a entrevista prática.',
    'Svargrond ensina que existe frio e existe esperar o último integrante da party. O segundo parece durar uma estação inteira.',
    'Yalahar oferece muitos caminhos e o minotaur oferece uma opinião firme sobre sua visita. Atendimento direto: sem formulário e sem pesquisa de satisfação.',
    'O server save é a pausa oficial de Tibia. Minha lista de tarefas aproveita para lembrar que também existe um mundo do lado de fora da janela.',
    'Shared XP é trabalho em equipe. A primeira etapa consiste em juntar o grupo; a segunda é descobrir quem ainda está comprando alguma coisa no Market.',
    'O knight abriu caminho e o grupo seguiu confiante. Eu segui olhando a backpack, porque coragem é boa, mas saber onde estão as potions também ajuda.',
    'O paladin trouxe munição, distância e planejamento. Eu trouxe uma pergunta sobre loot que poderia perfeitamente ter esperado até o fim da hunt.',
    'O druid cuida de muita coisa ao mesmo tempo. Se ainda conseguiu responder no chat, considere isso uma demonstração extra de organização.',
    'O sorcerer chegou preparado para causar estrago. O Market já tinha feito a parte dele quando o grupo foi comprar os suprimentos.',
    'Ham na backpack é provisão; vinte itens sem uso são uma coleção. A dificuldade começa quando o colecionador precisa admitir que também precisa de cap.',
    'Uma Boots of Haste dá vontade de acelerar a aventura. Infelizmente, chegar mais rápido ao depot não faz a arrumação das backpacks terminar mais cedo.',
    'A hunt começou com “só mais um pouco”. Algumas backpacks depois, essa unidade de tempo já precisava de uma definição oficial no calendário.',
    'O respawn tem uma pontualidade admirável. Já o amigo que disse “volto em dois minutos” parece seguir um calendário exclusivo de outra dimensão.',
    'A melhor parte de voltar à cidade é contar a aventura. A segunda é vender o loot antes que a calculadora peça uma versão mais realista da história.',
    'Em Tibia, todo aventureiro carrega sonhos na backpack. Eu carrego os meus entre uma rope, algumas potions e coisas que jurei vender na última viagem.',
)

_lock = threading.Lock()
_fila = []
_ultima = None


def proxima():
    """Embaralha um novo ciclo após 60 mensagens; o último item não se repete na virada."""
    global _ultima
    with _lock:
        if not _fila:
            _fila.extend(MENSAGENS)
            random.shuffle(_fila)
            if _fila[-1] == _ultima:
                _fila[0], _fila[-1] = _fila[-1], _fila[0]
        _ultima = _fila.pop()
        return _ultima


def do_dia(dia, chave=''):
    """Frase do dia pela data (date): avança uma por dia, sem repetir em 60 dias nem depender da sessão. `chave` desloca o ponto de partida por perfil."""
    inicio = int.from_bytes(hashlib.sha256(chave.encode()).digest()[:4])
    return MENSAGENS[(dia.toordinal() + inicio) % len(MENSAGENS)]
