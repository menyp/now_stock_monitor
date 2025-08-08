// File: js_for_ACL.js
// Purpose: ServiceNow script to count and validate sys_security_acl records with sys_sg prefix

// Basic ServiceNow script to count sys_security_acl records with sys_sg prefix
var recordCount = 0;
var uniqueNames = {};

// Query all ACL records with names starting with "sys_sg"
var gr = new GlideRecord('sys_security_acl');
gr.addQuery('name', 'STARTSWITH', 'sys_sg');
gr.query();

// Count records and track unique names
while (gr.next()) {
    recordCount++;
    var aclName = gr.getValue('name');
    uniqueNames[aclName] = true;
}

// Output results
gs.info('=== SYS_SECURITY_ACL VALIDATION REPORT ===');
gs.info('Total records with name prefix "sys_sg": ' + recordCount);
gs.info('Unique ACL names with prefix "sys_sg": ' + Object.keys(uniqueNames).length);

// Optional: List the first 10 unique names as a sample
var namesList = Object.keys(uniqueNames);
if (namesList.length > 0) {
    gs.info('Sample of unique names (up to 10):');
    for (var i = 0; i < Math.min(namesList.length, 10); i++) {
        gs.info(' - ' + namesList[i]);
    }
}

gs.info('=== END OF REPORT ===');
