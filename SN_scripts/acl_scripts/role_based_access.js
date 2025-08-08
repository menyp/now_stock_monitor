/**
 * Role-based Access Control Script for ServiceNow
 * 
 * Purpose: Controls access to records based on user roles
 * Type: ACL Script
 * 
 * @param {GlideRecord} current - The current record being accessed
 * @param {GlideUser} user - The user attempting to access the record
 * @returns {Boolean} Whether the user has access to the record
 */
function aclScript(current, user) {
    // Check if user has admin role
    if (user.hasRole('admin')) {
        return true;
    }
    
    // Check if user has specific role needed for this record
    if (user.hasRole('itil') && current.assigned_to == user.getID()) {
        return true;
    }
    
    // Check if user is in the assignment group
    if (current.assignment_group.canRead() && 
        user.isMemberOf(current.assignment_group)) {
        return true;
    }
    
    return false;
}
