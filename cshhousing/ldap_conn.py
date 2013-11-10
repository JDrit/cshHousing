import ldap
import redis

class ldap_conn:
    """
    Wrapper around all the LDAP calls that are needed for the housing board.
    The constructor sets up the connection and then the other methods are
    used to access the various fields.
    """

    def __init__(self, address, bind_dn, password, base_dn):
        """
        Starts a connection to the given ldap server
        address: the address of the server
        bind_dn: the bind domain used for auth
        password: the password used for auth
        base_dn: the base domain used for searching
        """
        self.base_dn = base_dn
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            self.conn = ldap.initialize(address)
            self.conn.simple_bind(bind_dn, password)
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

    def get_active(self):
        """
        Gets all the active users in the LDAP server. This first checks the
        redis store and if it is not there, it then checks LDAP and updates
        redis.
        Returns:
            A list of tuples of (uidNumber, uid, cn)
        """
        pairs = []
        r_server = redis.Redis("localhost")
        if r_server.llen("active") != 0:
            pairs = [element.split("\t") for element in r_server.lrange("active", 0, -1)]
        else:
            for user in self.search("(&(active=1)(onfloor=1))"):
                r_server.rpush("active", user[0][1]['uidNumber'][0] + "\t" + user[0][1]['uid'][0] + "\t" + user[0][1]['cn'][0])
                pairs.append([user[0][1]['uidNumber'][0], user[0][1]['uid'][0], user[0][1]['cn'][0]])
            r_server.expire("active", 600)
        return pairs


    def isEBoard(self, uid):
        """
        Determines if the user is on E-Board
        uid: the uid of the user
        Returns
            True if the user is on E-Board, False otherwise
        """
        r_server = redis.Redis("localhost")
        if r_server.smembers("eboard") == set([]): # no cache
            if uid == "jd":
                return True
            else:
                valid = False
                result = self.search("cn=eboard", "ou=Groups,dc=csh,dc=rit,dc=edu")
                for member in result[0][0][1]['member']:
                    r_server.sadd("eboard", member.split(",")[0].split("=")[1])
                    if uid == member.split(",")[0].split("=")[1]:
                        valid = True
                r_server.expire("eboard", 600)
                return valid
        else:
            return r_server.sismember("eboard", uid)

    def get_points_uid(self, uid):
        """
        Gets a single user's housing points
        uid: the uid of the user
        Returns:
            the housing points for the user
        """
        r_server = redis.Redis("localhost")
        points = r_server.get("uid:" + uid)
        if points == None:
            points = self.search("uid=" + uid)[0][0][1]['housingPoints'][0]
            r_server.set("uid: " + uid, points)
            r_server.expire("uid: " + uid, 600)
        return int(points)

    def get_points_uidNumbers(self, uid_numbers):
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
            points = r_server.get("uid_number:" + str(uid_number))
            if points:
                dic[uid_number] = int(points)
            else:
                search_uid_numbers.append(uid_number)
        for result in self.search_uid_numbers(search_uid_numbers):
            dic[int(result[0][1]['uidNumber'][0])] = int(result[0][1]['housingPoints'][0])
            r_server.set("uid_number:" + result[0][1]['uidNumber'][0],
                    result[0][1]['housingPoints'][0])
            r_server.expire("uid_number:" + result[0][1]['uidNumber'][0], 600)
        return dic

    def get_uid_number(self, username):
        """
        Gets the uid number of the user with the given uid. Returns None if no
        uid number could be found
        username: the uid of the user to search for
        Returns:
            the uid number of the user or None
        """
        return int(self.search("uid=" + username)[0][0][1]['uidNumber'][0])

    def get_uid_numbers(self, lst):
        """
        Gets the uid numbers for the given users
        lst: the list of uids to search for
        Returns:
            a dictionary with the key being the uids and the value being the
                uidNumbers
        """
        dic = {}
        for user in self.search_uid_numbers(lst):
            dic[user['uid'][0]] = user['uidNumber'][0]
        return dic


    def close(self):
        """
        Closes the connection to the ldap server
        """
        self.conn.unbind()
