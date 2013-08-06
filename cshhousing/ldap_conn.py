import ldap

class ldap_conn:
    def __init__(self, address, bind_dn, password, base_dn):
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
            self.conn = ldap.initialize(address)
            self.conn.simple_bind(bind_dn, password)
            self.base_dn = base_dn
        except ldap.LDAPError, e:
            print e

    def search(self, search_filter):
        data = []
        scope = ldap.SCOPE_SUBTREE
        result_id = self.conn.search(self.base_dn, scope, search_filter, None)
        while True:
            result_type, result_data = self.conn.result(result_id, 0)
            if result_data == []:
                break
            else:
                if result_type == ldap.RES_SEARCH_ENTRY:
                    data.append(result_data)
        return data


    def search_uids(self, uids):
        if len(uids) == 1:
            search_filter = '(uidNumber=' + str(uids[0]) + ')'
        else:
            search_filter = '(|'
            for uid in uids:
                search_filter += '(uidNumber=' + str(uid) + ')'
            search_filter += ')'
        return self.search(search_filter)

    def get_active(self):
        return self.search("active=1")

    def isEBoard(self, uid):
        return True

    def get_points_uid(self, uid):
            return 2

    def get_points_uidNumbers(self, uids):
        dic = {}
        for uid in uids:
            dic[uid] = 2
        return dic

    def get_uid_number(self, username):
        data = []
        scope = ldap.SCOPE_SUBTREE
        search_filter = 'uid=' + username
        result_id = self.conn.search(self.base_dn, scope, search_filter, None)
        result_type, result_data = self.conn.result(result_id, 0)
        if result_data == []:
            return None
        else:
            return int(result_data[0][1]['uidNumber'][0])

    def close(self):
        self.conn.unbind()
