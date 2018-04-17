from lxml import html, etree
from datetime import datetime
from Game import Game
from pytz import timezone
from Service import Service
import requests
import re

squadre = {
	'TAQ': 'Aquilotti',
    'U13/M': 'Under 13',
    'U14/M': 'Under 14',
    'U15/M': 'Under 15',
    'U16/M': 'Under 16',
    'U17/M': 'Under 17',
    'U18/M': 'Under 18',
    'U20': 'Under 20',
    'PM': 'Promozione',
    'D': 'Serie D',
    'OPENM': 'Coppa Trentino'
}

romeTimeZone = timezone('Europe/Rome')

localEvents = []

#Inizializzo classe di support per Google Calendar
service = Service()

# Scarico la homepage del sito Fip Trentino
home = requests.post('http://fip.it/FipWeb/ajaxRisultatiGetMenuCampionati.aspx', data={'ar':'1', 'com':'RTN', 'IDProvincia':'TN', 'IDRegione':'TN','turno':'1'})

# Cerco i vari link delle categorie
for m in re.finditer('getRisultatiPartite\(\'RTN\', \'(?P<sesso>[MF])\', \'(?P<campionato>[^\']+)\', \'(?P<fase>[^\']+)\', \'(?P<codice>[^\']+)\', \'(?P<andata>\d)\', \'(?P<turno>\d+)\', \'(?P<idregione>[^\']*)\', \'(?P<idprovincia>[^\']*)\'\)', home.text):
    campionato = m.group('campionato')
    if campionato in squadre.keys() and service.existCalendar(squadre[campionato]):
        codice = m.group('codice')
        fase = m.group('fase')
        andata = m.group('andata')
        turno = m.group('turno')
        sesso = m.group('sesso')
        idregione = m.group('idregione')
        idprovincia = m.group('idprovincia')
        print('_' * 30)
        print()
        print(f' {squadre[campionato]} '.center(30, '-'))
        print()

        # Scarico la pagina con le date della categoria corrente
        # page = requests.post(f'http://fip.it/FipWeb/ajaxRisultatiGetPartite.aspx', data={'com':'RTN', 'sesso': sesso, 'IDRegione':idregione, 'IDProvincia':idprovincia, 'camp':campionato, 'fase':fase, 'girone':codice, 'ar':andata, 'turno':turno})
        page = requests.post(f'http://fip.it/FipWeb/ajaxRisultatiGetPartite.aspx', data={'com':'RTN', 'sesso': sesso, 'camp':campionato, 'fase':fase, 'girone':codice, 'ar':andata, 'turno':turno})

        # Cerco i link di tutte le giornate del campionato
        tree = html.fromstring(f'<div>{page.text}</div>')
        for m in re.finditer('getRisultatiPartite\(\'RTN\', \'(?P<sesso>[MF])\', \'(?P<campionato>[^\']+)\', \'(?P<fase>[^\']+)\', \'(?P<codice>[^\']+)\', \'(?P<andata>\d)\', \'(?P<turno>\d+)\', \'(?P<idregione>[^\']*)\', \'(?P<idprovincia>[^\']*)\'\)', etree.tostring(tree.xpath('//div[@class="hidden-xs"]')[0]).decode()):
            campionato = m.group('campionato')
            codice = m.group('codice')
            fase = m.group('fase')
            andata = m.group('andata')
            turno = m.group('turno')
            sesso = m.group('sesso')
            idregione = m.group('idregione')
            idprovincia = m.group('idprovincia')
            # Scarico la pagina della singola giornata del campionato
            # giornata = requests.post(f'http://fip.it/FipWeb/ajaxRisultatiGetPartite.aspx', data={'camp':campionato, 'ar':andata, 'com':'RTN', 'fase':fase, 'girone':codice, 'IDProvincia':idprovincia, 'IDRegione':idregione, 'sesso':sesso, 'turno':turno})
            giornata = requests.post(f'http://fip.it/FipWeb/ajaxRisultatiGetPartite.aspx', data={'camp':campionato, 'ar':andata, 'com':'RTN', 'fase':fase, 'girone':codice, 'sesso':sesso, 'turno':turno})
            tree = html.fromstring(f'<div>{giornata.content}</div>')
            # Scorro le partite e individuo squadre, data e luogo
            squadre1 = tree.xpath('//td[@class="nome-squadra nome-squadra-1"]')
            risultati1 = tree.xpath('//td[@class="risultato-squadra risultato-squadra-1"]')
            risultati2 = tree.xpath('//td[@class="risultato-squadra risultato-squadra-2"]')
            squadre2 = tree.xpath('//td[@class="nome-squadra nome-squadra-2"]')
            places = tree.xpath('//td[@class="luogo-arbitri"]')
            dates = tree.xpath('//td[@class="luogo-arbitri"]/strong/child::text() | //td[@class="luogo-arbitri"]/strong/font/child::text()')
            for i in range(len(risultati1)):
                if risultati1[i].text and risultati2[i].text:
                    result = f'{risultati1[i].text}-{risultati2[i].text}'
                else:
                    result = '-'
                # print(squadre1[i].text, risultati1[i].text, risultati2[i].text, squadre2[i].text, places[i].text, dates[i])
                # Inizializzo l'oggetto Game
                game = Game(
                    league=squadre[campionato],
                    teamA=squadre1[i].text,
                    teamB=squadre2[i].text,
                    result=result,
                    place=re.sub(r'\\t|\\n|\\r', '', places[i].text),
                    dateData=dates[i]
                )
                if game.isGardolo or game.isUnder20:
                    if game.futureGame:
                        localEvents.append(game)
                        service.saveGame(game)
                        print(f'{game.teamA} - {game.teamB}: {game.gameday} {game.time}')
                    else:
                        print(f'{game.teamA} - {game.teamB}: {game.result}')

# Controllo se ci sono partite su Calendar non più presenti sul sito Fip.
# In questo caso devo cancellarle da Calendar perché con tutta probabilità
# sono state spostate
for remoteEvent in service.remoteEvents:
    localEvent = [l for l in localEvents
        if remoteEvent['start']['dateTime'] == romeTimeZone.localize(datetime.combine(l.gameday, l.time)).isoformat('T') and remoteEvent['summary'] in [f'{league}: {l.teamA} vs {l.teamB}' for league in l.league]]
    if len(localEvent) == 0:
        service.deleteGame(remoteEvent)
        print('Cancellato:', remoteEvent['summary'], remoteEvent['start']['dateTime'])
        
