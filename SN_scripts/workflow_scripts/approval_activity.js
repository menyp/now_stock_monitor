/**
 * Workflow Approval Activity Script
 * 
 * Purpose: Custom approval activity for change requests
 * Type: Workflow Script
 * Workflow: Change Request Approval
 */
function runActivity(/* GlideRecord */ current, /* Workflow.Activity */ activity) {
    
    // Get necessary variables from the workflow
    var approvalGroup = activity.scratchpad.approval_group;
    var requiredApprovers = activity.scratchpad.required_approvers || 1;
    var timeout = activity.scratchpad.timeout || 86400; // 24 hours in seconds
    
    // Create approval record
    var approval = new GlideRecord('sysapproval_approver');
    approval.initialize();
    approval.sysapproval = current.sys_id;
    approval.group = approvalGroup;
    approval.comments = 'Approval requested for ' + current.number + ': ' + current.short_description;
    approval.due_date = new GlideDateTime();
    approval.due_date.addSeconds(timeout);
    approval.state = 'requested';
    approval.insert();
    
    // Add approval to activity scratchpad
    activity.scratchpad.approval_sys_id = approval.sys_id.toString();
    activity.scratchpad.approvers_completed = 0;
    
    // Return 'wait' to pause the workflow until approval is complete
    return 'wait';
}

function checkCondition(/* GlideRecord */ current, /* Workflow.Activity */ activity) {
    
    // Get the approval record
    var approvalId = activity.scratchpad.approval_sys_id;
    var approval = new GlideRecord('sysapproval_approver');
    if (!approval.get(approvalId)) {
        return 'rejected'; // Approval not found
    }
    
    // Check approval state
    if (approval.state == 'approved') {
        return 'approved';
    } else if (approval.state == 'rejected') {
        return 'rejected';
    } else if (isTimedOut(approval, activity)) {
        // Auto-reject if timed out
        approval.state = 'rejected';
        approval.comments = 'Automatically rejected due to timeout';
        approval.update();
        return 'rejected';
    }
    
    // Still waiting for approval
    return 'wait';
}

function isTimedOut(approval, activity) {
    var now = new GlideDateTime();
    var dueDate = new GlideDateTime();
    dueDate.setValue(approval.due_date);
    
    return now.compareTo(dueDate) > 0;
}
