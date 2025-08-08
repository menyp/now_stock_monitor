/**
 * Automatic Incident Assignment
 * 
 * Purpose: Automatically assigns incidents based on category and priority
 * Type: Business Rule (before insert/update)
 * Table: incident
 */
(function executeRule(current, previous /*null when async*/) {
    
    // Only proceed if not already assigned
    if (current.assigned_to.changes() || current.assigned_to.nil()) {
        
        var category = current.category.toString();
        var priority = parseInt(current.priority);
        
        // Define assignment logic
        if (category === 'network') {
            assignToNetworkTeam(current, priority);
        } else if (category === 'hardware') {
            assignToHardwareTeam(current, priority);
        } else if (category === 'software') {
            assignToSoftwareTeam(current, priority);
        } else {
            assignToServiceDesk(current);
        }
    }
    
    function assignToNetworkTeam(incident, priority) {
        var groupId = getGroupId('Network Support');
        incident.assignment_group = groupId;
        
        // For high priority, assign to team lead
        if (priority === 1) {
            var teamLead = getTeamLead(groupId);
            if (teamLead) {
                incident.assigned_to = teamLead;
            }
        }
    }
    
    function assignToHardwareTeam(incident, priority) {
        incident.assignment_group = getGroupId('Hardware Support');
    }
    
    function assignToSoftwareTeam(incident, priority) {
        incident.assignment_group = getGroupId('Software Support');
    }
    
    function assignToServiceDesk(incident) {
        incident.assignment_group = getGroupId('Service Desk');
    }
    
    function getGroupId(groupName) {
        var grp = new GlideRecord('sys_user_group');
        grp.addQuery('name', groupName);
        grp.query();
        if (grp.next()) {
            return grp.sys_id;
        }
        return '';
    }
    
    function getTeamLead(groupId) {
        var grRole = new GlideRecord('sys_user_grmember');
        grRole.addQuery('group', groupId);
        grRole.addQuery('role', 'manager');
        grRole.query();
        if (grRole.next()) {
            return grRole.user;
        }
        return '';
    }
    
})(current, previous);
