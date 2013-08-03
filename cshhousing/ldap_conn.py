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

    def search(self, uids):
        data = []
        scope = ldap.SCOPE_SUBTREE
        search_filter = '(|'
        for uid in uids:
            search_filter += '(uidNumber=' + str(uid) + ')'
        search_filter += ')'
        result_id = self.conn.search(self.base_dn, scope, search_filter, None)
        result_type, result_data = self.conn.result(result_id, 0)
        while True:
            result_type, result_data = self.conn.result(result_id, 0)
            if result_data == []:
                break
            else:
                if result_type == ldap.RES_SEARCH_ENTRY:
                    data.append(result_data)
        return data

    def get_active(self):
        data = []
        scope = ldap.SCOPE_SUBTREE
        search_filter = 'active=1'
        result_id = self.conn.search(self.base_dn, scope, search_filter, None)
        while True:
            result_type, result_data = self.conn.result(result_id, 0)
            if result_data == []:
                break
            else:
                if result_type == ldap.RES_SEARCH_ENTRY:
                    data.append(result_data)

        return data

    def isEBoard(self, uid):
        return True

    def close(self):
        self.conn.unbind()
