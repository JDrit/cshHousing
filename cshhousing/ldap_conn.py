import ldap
import redis

class ldap_conn:
    """
    Wrapper around all the LDAP calls that are needed for the housing board.
    The constructor sets up the connection and then the other methods are
    used to access the various fields.
    """

    def __init__(self, request):
        """
        Starts a connection to the given ldap server
        address: the address of the server
        bind_dn: the bind domain used for auth
        password: the password used for auth
        base_dn: the base domain used for searching
        """
        settings = request.registry.settings
        self.base_dn = settings['base_dn']
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            self.conn = ldap.initialize(settings['address'])
            self.conn.simple_bind(settings['bind_dn'], settings['password'])
        except ldap.LDAPError, error:
            print 'ERROR:', error

    def search(self, search_filter, base_dn = None):
        """
        Searches the ldap server with the given search filter and returns
        the results
        search_filter: the search filter used in the search
        Returns:
            the list of results
        """
        if not base_dn: base_dn = self.base_dn
        data = []
        scope = ldap.SCOPE_SUBTREE
        result_id = self.conn.search(base_dn, scope, search_filter, None)
        while True:
            result_type, result_data = self.conn.result(result_id, 0)
            if result_data == []:
                break
            else:
                if result_type == ldap.RES_SEARCH_ENTRY:
                    data.append(result_data)
        return data


    def search_uid_numbers(self, uids):
        """
        Gets the ldap entires for all users in the given list
        uids: the uids of the user to search for
        Returns:
            a list of the users that were asked for
        """
        if len(uids) == 1:
            search_filter = '(uidNumber=' + str(uids[0]) + ')'
        else:
            search_filter = '(|'
            for uid in uids:
                search_filter += '(uidNumber=' + str(uid) + ')'
            search_filter += ')'
        return self.search(search_filter)


    def get_uid_number(self, username):
        """
        Gets the uid number of the user with the given uid. Returns None if no
        uid number could be found
        username: the uid of the user to search for
        Returns:
            the uid number of the user or None
        """
        return int(self.search("uid=" + username)[0][0][1]['uidNumber'][0])

    def get_username(self, uid_number):
        return self.search("uidNumber=" + int(uid_number))[0][0][1]['uid'][0]

    def close(self):
        """
        Closes the connection to the ldap server
        """
        self.conn.unbind()


def isEBoard(uid, request):
    """
    Determines if the user is on E-Board
    uid: the uid of the user
    Returns
        True if the user is on E-Board, False otherwise
    """
    return uid == 'jd' or uid == 'keller'

def get_points_uid(uid, request):
    """
    Gets a single user's housing points
    uid: the uid of the user
    Returns:
        the housing points for the user
    """
    r_server = redis.Redis("localhost")
    points = r_server.get("uid_to_points:" + uid)
    if points == None:
        conn = ldap_conn(request)
        points = conn.search("uid=" + uid)
        conn.close()
        points = int(points[0][0][1]['housingPoints'][0])
        r_server.set("uid_to_points: " + uid, points)
        r_server.expire("uid_to_points: " + uid, 600)
    return int(points)

def get_username(uid_number, request):
    """
    Gets the username for the username with the given uid number.
    Adds it to the cached data.
    Arguments:
        uid_number: the uid number for the user
    Returns the username for the user
    """
    r_server = redis.Redis('localhost')
    username = r_server.get('uid_to_username:' + int(uid_number))
    if username:
        conn = ldap_conn(request)
        username = conn.get_username(uid_number)
        conn.close()
        r_server.set('uid_to_username:' + int(uid_number), username)
        r_server.expire('uid_to_username:' + int(uid_number), 600)
    return username

def get_uid_number(username, request):
    r_server = redis.Redis('localhost')
    uid_number = r_server.get('username_to_uid_number:' + username)
    if uid_number == None:
        conn = ldap_conn(request)
        uid_number = conn.get_uid_number(username)
        conn.close()
        r_server.set('username_to_uid_number:' + username, uid_number)
        r_server.expire('username_to_uid_number:' + username, 600)
    return int(uid_number)

def get_active(request):
    """
    Gets all the active users in the LDAP server.
    This first checks the redis store and if it is not there,
    it then checks LDAP and updates redis.
    Returns:
        A list of tuples of (uidNumber, uid, cn)
    """
    pairs = []
    r_server = redis.Redis("localhost")
    if r_server.llen("active") != 0:
        pairs = [element.split("\t") for element in r_server.lrange("active", 0, -1)]
    else:
        conn = ldap_conn(request)
        for user in conn.search("(onfloor=1)"):
            r_server.rpush("active",
                    user[0][1]['uidNumber'][0] + "\t" +
                    user[0][1]['uid'][0] + "\t" +
                    user[0][1]['cn'][0])
            pairs.append([user[0][1]['uidNumber'][0],
                user[0][1]['uid'][0], user[0][1]['cn'][0]])
        r_server.expire("active", 600)
        conn.close()
    return pairs

def get_points_uidNumbers(uid_numbers, request):
    """
    Takes a list of uid numbers and returns the housing points for each. The
    results are cached in redis for future use
    uid_numbers: the list of uid numbers represeting the users
    Returns:
        A dictionary of the points with the key being the uid number and
            the value being the amount of points
    """
    dic = {}
    search_uid_numbers = []
    r_server = redis.Redis("localhost")
    for uid_number in uid_numbers:
        points = r_server.get("uid_number_to_points:" + str(uid_number))
        if points:
            dic[uid_number] = int(points)
        else:
            search_uid_numbers.append(uid_number)
    if search_uid_numbers:
        conn = ldap_conn(request)
        for result in conn.search_uid_numbers(search_uid_numbers):
            dic[int(result[0][1]['uidNumber'][0])] = int(result[0][1]['housingPoints'][0])
            r_server.set("uid_number_to_points:" + result[0][1]['uidNumber'][0],
                    int(result[0][1]['housingPoints'][0]))
            r_server.expire("uid_number_to_points:" + result[0][1]['uidNumber'][0], 600)
        conn.close()
    return dic


