from authomatic.providers import oauth2
import authomatic

CONFIG = {

    'google': {

        'class_': oauth2.Google,

        # Facebook is an AuthorizationProvider too.
        'consumer_key': '158766466665-homepmhdjcpbthrq0pkk28qgvqmn2hra.apps.googleusercontent.com',
        'consumer_secret': 'op-4ek2vM_5Gn9_IMvtpymgs',
        'id': authomatic.provider_id(),
        # But it is also an OAuth 2.0 provider and it needs scope.
        'scope': oauth2.Google.user_info_scope + ['https://mail.google.com/','profile', 'https://www.google.com/m8/feeds/'],
    }
}
