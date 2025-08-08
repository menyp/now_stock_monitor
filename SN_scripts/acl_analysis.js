// Script to list and count all sys_sg records with decision_type = "allow"
var allowCount = 0;
var uniqueNames = {};
var operationCounts = {
    create: 0,
    read: 0,
    write: 0,
    delete: 0,
    other: 0
};

// Query all ACL records with names starting with "sys_sg" and decision_type = "allow"
var gr = new GlideRecord('sys_security_acl');
gr.addQuery('name', 'STARTSWITH', 'sys_sg');
gr.addQuery('decision_type', 'allow');
gr.orderBy('name');
gr.orderBy('operation');
gr.query();

gs.info('=== SYS_SG RECORDS WITH DECISION_TYPE "ALLOW" (SHOWS AS "ALLOW IF" IN UI) ===');

// Process records
while (gr.next()) {
    allowCount++;
    var aclName = gr.getValue('name');
    var operation = gr.getValue('operation');
    var sysId = gr.getUniqueValue();
    
    // Track unique names
    if (!uniqueNames[aclName]) {
        uniqueNames[aclName] = {
            operations: [],
            count: 0
        };
    }
    uniqueNames[aclName].operations.push(operation);
    uniqueNames[aclName].count++;
    
    // Count by operation type
    if (operation === 'create') {
        operationCounts.create++;
    } else if (operation === 'read') {
        operationCounts.read++;
    } else if (operation === 'write') {
        operationCounts.write++;
    } else if (operation === 'delete') {
        operationCounts.delete++;
    } else {
        operationCounts.other++;
    }
}
