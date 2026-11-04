# language: fr
Fonctionnalité: Sélecteur de profil device

  Scénario: Le profil par défaut est affiché
    Étant donné le mode du bridge est à proxy
    Et le bridge sert la WebUI construite
    Quand j'ouvre la page d'accueil
    Alors le sélecteur de profil est visible
    Et le profil sélectionné est « inspirair-sc150 »

  Scénario: Changement de profil via le dropdown
    Étant donné le mode du bridge est à proxy
    Et le bridge sert la WebUI construite
    Quand j'ouvre la page d'accueil
    Et je change le profil pour « inspirair-sc150 »
    Alors le profil sélectionné est « inspirair-sc150 »
    Et le profil « inspirair-sc150 » est actif côté API
