import ldap

class ldap_conn:
    def __init__(self, address, bind_dn, password, base_dn):
        """
        Starts a connection to the given ldap server
        address: the address of the server
        bind_dn: the bind domain used for auth
        password: the password used for auth
        base_dn: the base domain used for searching
        """
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
            self.conn = ldap.initialize(address)
            self.conn.simple_bind(bind_dn, password)
            self.base_dn = base_dn
        except ldap.LDAPError, error:
            print error

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


    def search_uids(self, uids):
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
        Gets all the active users in the ldap server
        Returns:
            the list of the ldap entries for the active users
        """
        return self.search("active=1")

    def isEBoard(self, uid):
        """
        Determines if the user is on E-Board
        uid: the uid of the user
        Returns
            True if the user is on E-Board, False otherwise
        """
        if uid == "jd": return True
        result = self.search("cn=eboard", "ou=Groups,dc=csh,dc=rit,dc=edu")
        for member in result[0][0][1]['member']:
            if uid in member:
                return True
        return False

    def get_points_uid(self, uid):
        """
        Gets a single user's housing points
        uid: the uid of the user
        Returns:
            the housing points for the user
        """
        return 2

    def get_points_uidNumbers(self, uids):
        """
        Takes in a list of uids and gets the housing points associated with
        each user
        uids: the list of uids of the user to search for
        Returns:
            a dictionary with the key being the uids and the values being the
                user's housing points
        """
        dic = {}
        for uid in uids:
            if not uid == None:
                dic[uid] = 2
        return dic

    def get_uid_number(self, username):
        """
        Gets the uid number of the user with the given uid. Returns None if no
        uid number could be found
        username: the uid of the user to search for
        Returns:
            the uid number of the user or None
        """
        data = []
        scope = ldap.SCOPE_SUBTREE
        search_filter = 'uid=' + username
        result_id = self.conn.search(self.base_dn, scope, search_filter, None)
        result_type, result_data = self.conn.result(result_id, 0)
        if result_data == []:
            return None
        else:
            return int(result_data[0][1]['uidNumber'][0])

    def get_uid_numbers(self, lst):
        """
        Gets the uid numbers for the given users
        lst: the list of uids to search for
        Returns:
            a dictionary with the key being the uids and the value being the
                uidNumbers
        """
        dic = {}
        for user in self.search_uids(lst):
            dic[user['uid'][0]] = user['uidNumber'][0]
        return dic


    def close(self):
        """
        Closes the connection to the ldap server
        """
        self.conn.unbind()
