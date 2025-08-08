// File: js_for_ACL.js
// Purpose: ServiceNow script to count and validate sys_security_acl records with sys_sg prefix

// Buffer to collect all output except summary
var outputBuffer = '';

// Custom logging function to buffer output
function logToBuffer(message) {
    outputBuffer += message + '\n';
}

// Basic ServiceNow script to count sys_security_acl records with sys_sg prefix
var recordCount = 0;
var uniqueNames = {};
var allowIfCount = 0;
var uniqueAllowIfNames = {};
var nonAllowIfNames = {};

// Track operation counts for "Allow If" records
var operationCounts = {
    "create": 0,
    "read": 0,
    "write": 0,
    "delete": 0,
    "other": 0
};

// Track operations by ACL name
var aclOperations = {};

// Track roles for each ACL name
var aclRoles = {};

// CRUD operations we're checking for
var crudOperations = ['create', 'read', 'write', 'delete'];

// Role we're specifically checking for
var targetRole = 'mobile_admin';

// Pre-load roles information to avoid repeated queries
var aclRoleMap = {};
var rolesCache = {};

// Load all roles first
function preloadRoles() {
    gs.info('=== DEBUG: Starting role preload ===');
    
    // Cache user roles (sys_user_role) for quick lookup
    var roleGr = new GlideRecord('sys_user_role');
    roleGr.query();
    var roleCount = 0;
    while (roleGr.next()) {
        rolesCache[roleGr.sys_id + ''] = roleGr.name + '';
        roleCount++;
        
        // Debug if we found our target role
        if (roleGr.name == targetRole) {
            gs.info('DEBUG: Found target role "' + targetRole + '" with sys_id: ' + roleGr.sys_id);
        }
    }
    gs.info('DEBUG: Cached ' + roleCount + ' user roles');
    
    // Cache ACL role assignments (sys_security_acl_role)
    var aclRoleGr = new GlideRecord('sys_security_acl_role');
    aclRoleGr.addQuery('acl.name', 'STARTSWITH', 'sys_sg');
    aclRoleGr.query();
    
    var aclRoleCount = 0;
    var targetRoleCount = 0;
    
    while (aclRoleGr.next()) {
        var aclId = aclRoleGr.acl + '';
        var roleId = aclRoleGr.role + '';
        aclRoleCount++;
        
        if (!aclRoleMap[aclId]) {
            aclRoleMap[aclId] = [];
        }
        
        // Use the cached role name
        var roleName = rolesCache[roleId] || '';
        if (roleName) {
            aclRoleMap[aclId].push(roleName);
            
            // Count how many have our target role
            if (roleName == targetRole) {
                targetRoleCount++;
            }
        }
    }
    
    gs.info('DEBUG: Processed ' + aclRoleCount + ' ACL role assignments');
    gs.info('DEBUG: Found ' + targetRoleCount + ' ACLs with "' + targetRole + '" role');
    gs.info('=== DEBUG: Role preload complete ===');
}

// Get all roles for an ACL using the cached data
function getRolesForAcl(aclSysId) {
    return aclRoleMap[aclSysId] || [];
}

// Check if an ACL has the target role using the cached data
function hasTargetRole(aclSysId, role) {
    var roles = aclRoleMap[aclSysId] || [];
    
    // Loop through and check for case-insensitive match
    for (var i = 0; i < roles.length; i++) {
        if (roles[i].toLowerCase() == role.toLowerCase()) {
            return true;
        }
    }
    
    return false;
}

// Preload all roles data
preloadRoles();

// Add a direct check for mobile_admin role to confirm our data
function directRoleCheck() {
    var startTime = new Date().getTime();
    
    // Get sys_id of mobile_admin role
    var roleGr = new GlideRecord('sys_user_role');
    roleGr.addQuery('name', targetRole);
    // Only get the sys_id field to improve performance
    roleGr.setLimit(1);
    roleGr.query();
    
    if (!roleGr.next()) {
        gs.info('WARNING: Could not find "' + targetRole + '" role in sys_user_role table!');
        return;
    }
    
    var roleId = roleGr.sys_id + '';
    gs.info('DEBUG: Direct check - Found "' + targetRole + '" role with sys_id: ' + roleId);
    
    // Now count ACLs with this role directly
    var aclCount = 0;
    var aclList = [];
    
    var aclRoleGr = new GlideRecord('sys_security_acl_role');
    aclRoleGr.addQuery('role', roleId);
    aclRoleGr.addQuery('acl.name', 'STARTSWITH', 'sys_sg');
    // Only get fields we need
    aclRoleGr.setLimit(10); // Limit results for testing
    aclRoleGr.query();
    
    while (aclRoleGr.next() && aclCount < 5) {
        aclCount++;
        
        // Get ACL name for verification using dot-walking when possible
        var aclId = aclRoleGr.acl + '';
        var aclGr = new GlideRecord('sys_security_acl');
        if (aclGr.get(aclId)) {
            aclList.push(aclGr.name + '');
        }
    }
    
    gs.info('DEBUG: Direct check found ' + aclCount + ' ACLs with "' + targetRole + '" role');
    if (aclList.length > 0) {
        gs.info('DEBUG: Sample ACLs with this role: ' + aclList.join(', '));
    }
}

directRoleCheck();

// Query all ACL records with names starting with "sys_sg"
var gr = new GlideRecord('sys_security_acl');
gr.addQuery('name', 'STARTSWITH', 'sys_sg');
gr.query();

// Count records and track unique names
while (gr.next()) {
    recordCount++;
    var aclName = gr.getValue('name');
    var decisionType = gr.getValue('decision_type');
    
    // Track unique names
    if (!uniqueNames[aclName]) {
        uniqueNames[aclName] = true;
    }
    
    // Check if this is an "Allow If" record (stored as "allow" in the database)
    if (decisionType === 'allow') {
        allowIfCount++;
        uniqueAllowIfNames[aclName] = true;
        
        // Count operations for "Allow If" records
        var operation = gr.getValue('operation');
        if (operation === 'create') {
            operationCounts["create"]++;
        } else if (operation === 'read') {
            operationCounts["read"]++;
        } else if (operation === 'write') {
            operationCounts["write"]++;
        } else if (operation === 'delete') {
            operationCounts["delete"]++;
        } else {
            operationCounts["other"]++;
        }
        
        // Track operations by ACL name
        if (!aclOperations[aclName]) {
            aclOperations[aclName] = {
                'create': false,
                'read': false,
                'write': false,
                'delete': false,
                'other': false
            };
        }
        
        // Mark this operation as present for this ACL name
        aclOperations[aclName][operation] = true;
        
        // Initialize role tracking for this ACL name if needed
        if (!aclRoles[aclName]) {
            aclRoles[aclName] = {
                hasTargetRole: false,
                rolesList: []
            };
        }
        
        // Get sys_id of the current ACL record
        var aclSysId = gr.getUniqueValue();
        
        // Check if this ACL has the target role using cached data
        if (hasTargetRole(aclSysId, targetRole)) {
            aclRoles[aclName].hasTargetRole = true;
        }
        
        // Get all roles for this ACL using cached data
        var rolesList = getRolesForAcl(aclSysId);
        
        // Add new roles to the list
        for (var j = 0; j < rolesList.length; j++) {
            var role = rolesList[j];
            if (!aclRoles[aclName].rolesList.includes(role)) {
                aclRoles[aclName].rolesList.push(role);
            }
        }
    } else {
        // Track names of records that don't have "Allow If" decision type
        nonAllowIfNames[aclName] = decisionType || 'none';
    }
}

// Count unique names
var uniqueNameCount = Object.keys(uniqueNames).length;
var uniqueAllowIfNameCount = Object.keys(uniqueAllowIfNames).length;

// Function to generate a summary report
function generateSummary() {
    // Get the counts
    var uniqueNameCount = Object.keys(uniqueNames).length;
    var completeAclCount = completeAcls.length;
    var incompleteAclCount = incompleteAcls.length;
    
    // Count ACLs by category
    var starSuffixCount = 0;
    var dotCount = 0;
    var plainCount = 0;
    
    for (var i = 0; i < incompleteAcls.length; i++) {
        var acl = incompleteAcls[i];
        if (acl.name.endsWith('*')) {
            starSuffixCount++;
        } else if (acl.name.indexOf('.') >= 0) {
            dotCount++;
        } else {
            plainCount++;
        }
    }
    
    // Count ACLs with mobile_admin role
    var withRoleCount = withTargetRole ? withTargetRole.length : 0;
    var withRolePercent = completeAclCount > 0 ? Math.round((withRoleCount / completeAclCount) * 100) : 0;
    
    var summaryReport = '';
    summaryReport += '\n**********************************************************\n';
    summaryReport += '***                                                  ***\n';
    summaryReport += '***       SUMMARY REPORT: ACL ROLE VALIDATION        ***\n';
    summaryReport += '***                                                  ***\n';
    summaryReport += '**********************************************************\n\n';
    summaryReport += 'TOTAL UNIQUE ACL NAMES: ' + uniqueNameCount + '\n\n';
    summaryReport += 'CRUD OPERATION BREAKDOWN:\n';
    summaryReport += ' ✓ ACLs WITH complete CRUD operations: ' + completeAclCount + ' (' + Math.round((completeAclCount/uniqueNameCount)*100) + '%)\n';
    summaryReport += ' ✗ ACLs MISSING some CRUD operations: ' + incompleteAclCount + ' (' + Math.round((incompleteAclCount/uniqueNameCount)*100) + '%)\n';
    summaryReport += '   └── With suffix "*": ' + starSuffixCount + '\n';
    summaryReport += '   └── With dots ".": ' + dotCount + '\n';
    summaryReport += '   └── Plain names: ' + plainCount + '\n';
    summaryReport += '   └── TOTAL: ' + (starSuffixCount + dotCount + plainCount) + ' (should equal ' + incompleteAclCount + ')\n\n';
    summaryReport += 'ROLE ANALYSIS (for complete ACLs only):\n';
    summaryReport += ' ✓ WITH "' + targetRole + '" role: ' + withRoleCount + ' (' + withRolePercent + '%)\n';
    summaryReport += ' ✗ WITHOUT "' + targetRole + '" role: ' + (completeAclCount - withRoleCount) + ' (' + (100 - withRolePercent) + '%)\n';
    summaryReport += '**********************************************************\n';
    
    return summaryReport;
}

// Output to buffer
logToBuffer('=== DETAILED SYS_SECURITY_ACL VALIDATION REPORT ===')
logToBuffer('Total records with name prefix "sys_sg": ' + recordCount);
logToBuffer('Total unique names with prefix "sys_sg": ' + uniqueNameCount);
logToBuffer('Total records with decision_type "Allow If": ' + allowIfCount);
logToBuffer('Total unique names with decision_type "Allow If": ' + uniqueAllowIfNameCount);

// Report operation counts for "Allow If" records
logToBuffer('\n=== OPERATION BREAKDOWN FOR "ALLOW IF" RECORDS ===');
logToBuffer('Create operations: ' + operationCounts["create"]);
logToBuffer('Read operations: ' + operationCounts["read"]);
logToBuffer('Write operations: ' + operationCounts["write"]);
logToBuffer('Delete operations: ' + operationCounts["delete"]);
logToBuffer('Other operations: ' + operationCounts["other"]);

// List the first 10 unique names as a sample
logToBuffer('\nSample of unique ACL names (up to 10):');
var uniqueNameKeys = Object.keys(uniqueNames);
for (var i = 0; i < Math.min(10, uniqueNameKeys.length); i++) {
    logToBuffer((i+1) + '. ' + uniqueNameKeys[i]);
}

var completeAcls = [];
var incompleteAcls = [];

// Debug what's in aclOperations
logToBuffer('DEBUG: aclOperations contains ' + Object.keys(aclOperations).length + ' entries');

// For each ACL name with "Allow If", check if it has all 4 CRUD operations
for (var aclName in aclOperations) {
    var operations = aclOperations[aclName];
    var hasAllCrud = true;
    
    // Check if all 4 CRUD operations are present
    for (var i = 0; i < crudOperations.length; i++) {
        var op = crudOperations[i];
        if (!operations[op]) {
            hasAllCrud = false;
            break;
        }
    }
    
    // If all 4 CRUD operations are present, add to complete ACLs list
    if (hasAllCrud) {
        completeAcls.push(aclName);
    } else {
        // Otherwise, track which operations are missing
        var missingOps = [];
        for (var i = 0; i < crudOperations.length; i++) {
            var op = crudOperations[i];
            if (!operations[op]) {
                missingOps.push(op);
            }
        }
        incompleteAcls.push({
            name: aclName,
            missingOperations: missingOps
        });
    }
}

// Dump some debugging information about the complete ACLs
logToBuffer('DEBUG: Found ' + completeAcls.length + ' complete ACLs');
logToBuffer('DEBUG: Sample of complete ACLs (up to 5):');
for (var i = 0; i < Math.min(5, completeAcls.length); i++) {
    logToBuffer('  ' + (i+1) + '. "' + completeAcls[i] + '"');
}

// Important: We need to track the complete ACLs separately and get their role information directly
// instead of trying to match between different queries

// We'll directly check if each complete ACL has the mobile_admin role
var withTargetRole = [];
var withoutTargetRole = [];
var directCheckMap = {};

// First get the sys_id of the mobile_admin role
var roleId = '';
var roleGr = new GlideRecord('sys_user_role');
roleGr.addQuery('name', targetRole);
roleGr.setLimit(1);
roleGr.query();

if (roleGr.next()) {
    roleId = roleGr.sys_id + '';
    logToBuffer('Found target role "' + targetRole + '" with sys_id: ' + roleId);
} else {
    logToBuffer('WARNING: Could not find role "' + targetRole + '"');
    // If role doesn't exist, we can't proceed with role checks
    roleId = null;
}

// NEW APPROACH: Directly check each complete ACL for the mobile_admin role
// This avoids any issues with name matching

if (roleId) {
    logToBuffer('Starting DIRECT check of ' + completeAcls.length + ' complete ACLs for ' + targetRole + ' role');
    
    // This will track which complete ACLs have the role
    var directRoleCountByName = {};
    var checkedAcls = 0;
    
    // For each complete ACL name, find the corresponding ACL record(s)
    // and check if any have the role assigned
    for (var i = 0; i < completeAcls.length; i++) {
        var aclName = completeAcls[i];
        directRoleCountByName[aclName] = 0; // Initialize counter
        
        // Get all ACL records with this name
        var aclGr = new GlideRecord('sys_security_acl');
        aclGr.addQuery('name', aclName);
        aclGr.addQuery('decision_type', 'allow'); // Only 'Allow If' records
        aclGr.query();
        
        // Check each matching ACL record
        while (aclGr.next()) {
            checkedAcls++;
            var aclId = aclGr.sys_id + '';
            
            // Check if this ACL has the role assigned
            var aclRoleGr = new GlideRecord('sys_security_acl_role');
            aclRoleGr.addQuery('acl', aclId);
            aclRoleGr.addQuery('role', roleId);
            aclRoleGr.setLimit(1);
            aclRoleGr.query();
            
            if (aclRoleGr.hasNext()) {
                // This ACL has the mobile_admin role
                directRoleCountByName[aclName]++;
                
                // Debug output for the first few matches
                if (withTargetRole.length < 5) {
                    logToBuffer('DEBUG: Found match - ACL "' + aclName + '" has ' + targetRole + ' role');
                }
            }
        }
        
        // If any records for this ACL name had the role, consider this ACL to have the role
        if (directRoleCountByName[aclName] > 0) {
            withTargetRole.push(aclName);
        } else {
            withoutTargetRole.push(aclName);
        }
    }
    
    logToBuffer('DEBUG: Checked ' + checkedAcls + ' total ACL records');
    logToBuffer('DEBUG: ' + withTargetRole.length + ' out of ' + completeAcls.length + ' complete ACLs have the ' + targetRole + ' role');
    
    // Show some sample ACLs that have the role
    if (withTargetRole.length > 0) {
        logToBuffer('DEBUG: Sample ACLs WITH the "' + targetRole + '" role (up to 5):');
        for (var i = 0; i < Math.min(5, withTargetRole.length); i++) {
            logToBuffer('  ' + (i+1) + '. "' + withTargetRole[i] + '" - found in ' + directRoleCountByName[withTargetRole[i]] + ' ACL records');
        }
    }
    
    // Show some sample ACLs that don't have the role
    if (withoutTargetRole.length > 0) {
        logToBuffer('DEBUG: Sample ACLs WITHOUT the "' + targetRole + '" role (up to 5):');
        for (var i = 0; i < Math.min(5, withoutTargetRole.length); i++) {
            logToBuffer('  ' + (i+1) + '. "' + withoutTargetRole[i] + '"');
        }
    }
} else {
    // If we couldn't find the role, all ACLs are considered without the role
    withoutTargetRole = completeAcls.slice(); // Copy the array
    logToBuffer('WARNING: Could not find role "' + targetRole + '", so all ACLs are considered to not have it');
}

// Generate the summary now that all data is collected
var summaryText = generateSummary();

// We've completely replaced this section with the direct approach above

// Report on ACLs with complete/incomplete CRUD operations
logToBuffer('\n=== ACL CRUD OPERATION ANALYSIS ===')
logToBuffer('Total groups (unique ACL names): ' + uniqueNameCount);
logToBuffer(completeAcls.length + ' of the groups include the 4 Allow If CRUD operations');
logToBuffer(incompleteAcls.length + ' of the groups include fewer than four Allow If CRUD operations');

// Report on role validation for complete ACLs
logToBuffer('\n=== ROLE VALIDATION FOR COMPLETE ACLS ===');
var totalComplete = completeAcls.length;
var withRoleCount = withTargetRole.length;
var withoutRoleCount = withoutTargetRole.length;
var withRolePercent = Math.round((withRoleCount / totalComplete) * 100);
var withoutRolePercent = Math.round((withoutRoleCount / totalComplete) * 100);

logToBuffer('*** Script: ' + withRoleCount + ' out of ' + totalComplete + ' complete ACLs (' + withRolePercent + '%) have the "' + targetRole + '" role');
logToBuffer('*** Script: ' + withoutRoleCount + ' out of ' + totalComplete + ' complete ACLs (' + withoutRolePercent + '%) are missing the "' + targetRole + '" role');

// List ACLs without the target role
if (withoutTargetRole.length > 0) {
    logToBuffer('\nComplete ACLs missing the "' + targetRole + '" role:');
    for (var i = 0; i < withoutTargetRole.length; i++) {
        var aclName = withoutTargetRole[i];
        var roles = (aclRoles[aclName] && aclRoles[aclName].rolesList.length > 0) ? 
            ' (has roles: ' + aclRoles[aclName].rolesList.join(', ') + ')' : 
            ' (no roles assigned)';
        
        logToBuffer((i+1) + '. ' + aclName + roles);
    }
}

// Separate incomplete ACLs into three groups: those with suffix "*", those with dots, and others
var suffixStarAcls = [];
var withDotAcls = [];
var plainAcls = [];

for (var i = 0; i < incompleteAcls.length; i++) {
    var acl = incompleteAcls[i];
    if (acl.name.endsWith('*')) {
        suffixStarAcls.push(acl);
    } else if (acl.name.indexOf('.') >= 0) {
        withDotAcls.push(acl);
    } else {
        plainAcls.push(acl);
    }
}

// List ACLs missing CRUD operations
if (incompleteAcls.length > 0) {
    logToBuffer('\nGroups missing some Allow If CRUD operations: ' + incompleteAcls.length);
    
    // Report on records with suffix "*"
    logToBuffer('\nA. Records with suffix "*": ' + suffixStarAcls.length);
    for (var i = 0; i < suffixStarAcls.length; i++) {
        var acl = suffixStarAcls[i];
        logToBuffer('   ' + (i+1) + '. ' + acl.name + ' (missing: ' + acl.missingOperations.join(', ') + ')');
    }
    
    // Report on records with dots
    logToBuffer('\nB. Records with dots (.): ' + withDotAcls.length);
    for (var i = 0; i < withDotAcls.length; i++) {
        var acl = withDotAcls[i];
        logToBuffer('   ' + (i+1) + '. ' + acl.name + ' (missing: ' + acl.missingOperations.join(', ') + ')');
    }
    
    // Report on plain records (no * suffix and no dots)
    logToBuffer('\nC. Records without suffix "*" and without dots: ' + plainAcls.length);
    for (var i = 0; i < plainAcls.length; i++) {
        var acl = plainAcls[i];
        logToBuffer('   ' + (i+1) + '. ' + acl.name + ' (missing: ' + acl.missingOperations.join(', ') + ')');
    }
}

// List sample of records without "Allow If" decision type
var nonAllowIfList = Object.keys(nonAllowIfNames);
var nonAllowIfCount = nonAllowIfList.length;
logToBuffer('\n=== RECORDS WITHOUT "ALLOW IF" DECISION TYPE ===');
logToBuffer('Total records without "Allow If" decision type: ' + (recordCount - allowIfCount));
logToBuffer('Total unique names without "Allow If" decision type: ' + nonAllowIfCount);

if (nonAllowIfCount > 0) {
    logToBuffer('\nSample of ACL names without "Allow If" (up to 10):');
    for (var i = 0; i < Math.min(10, nonAllowIfCount); i++) {
        var name = nonAllowIfList[i];
        var type = nonAllowIfNames[name];
        logToBuffer((i+1) + '. ' + name + ' (decision_type: "' + type + '")');
    }
} else {
    logToBuffer('No records found without "Allow If" decision type.');
}

logToBuffer('=== END OF DETAILED REPORT ===');

// Output the summary first, then the detailed report
gs.info(summaryText);
gs.info(outputBuffer);
