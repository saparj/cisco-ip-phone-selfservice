# Risk Register

Lightweight risk tracking for the project.

## Scale

**Likelihood:** Low / Medium / High\
**Impact:** Low / Medium / High\
**Rating (suggested):** - Low = acceptable - Medium = needs mitigation
plan - High = must mitigate before production

------------------------------------------------------------------------

## Current Risks (Template)

  ---------------------------------------------------------------------------------------
    ID Risk          Likelihood   Impact   Rating   Mitigation / Control Owner   Status
  ---- ------------- ------------ -------- -------- -------------------- ------- --------
    R1 Admin         Medium       High     High     Add authentication + TBD     Open
       endpoints                                    IP allowlist;                
       exposed                                      restrict /admin in           
       without auth                                 Nginx                        

    R2 SQLite file   Low          Medium   Medium   Nightly backups +    TBD     Open
       corruption or                                tested restore;              
       data loss                                    migrate to Postgres          
                                                    for production               

    R3 Cisco XML     Medium       Medium   Medium   Maintain test        TBD     Open
       parsing                                      phones; validate XML         
       regressions                                  objects; avoid               
       across                                       unsupported elements         
       firmware                                                                  

    R4 Credential    Medium       High     High     Use env vars/secret  TBD     Open
       leakage when                                 store; never commit          
       adding                                       secrets; rotate              
       CUCM/Unity                                   credentials                  
       integration                                                               

    R5 Single host   Low          High     Medium   Document recovery;   TBD     Open
       failure (Pi)                                 image backup;                
                                                    consider VM/HA for           
                                                    production                   
  ---------------------------------------------------------------------------------------

------------------------------------------------------------------------
