# Effective AI Prompting for ServiceNow Script Development

This document provides tips on how to effectively prompt AI assistants like Cascade to develop and optimize ServiceNow scripts quickly.

## Sample Effective Prompt

```
I need to optimize a ServiceNow script that validates ACL records. The script should:

1. Find all sys_security_acl records with names starting with "sys_sg"
2. Identify which ACLs have complete CRUD operations ("create", "read", "write", "delete") and "Allow If" decision type
3. For each complete ACL, check if it has the "mobile_admin" role assigned
4. Create a summary report at the TOP of the output showing:
   - Total unique ACL names
   - How many have complete vs incomplete CRUD operations
   - For complete ACLs, how many have vs don't have the mobile_admin role
5. Add detailed information after the summary

Key requirements:
- Use direct role checking rather than name matching
- Format the summary with visual highlighting for quick scanning
- Make the script perform efficiently with many ACL records
- Include clear percentage calculations

Here's the existing code I want to improve: [paste current code]
```

## Tips for Working Efficiently with AI Coding Assistants

1. **Specify Output Format First**: Explain clearly where you want summary vs. details
   - "Put summary at the top with visual highlighting"
   - "Use percentage calculations for key metrics"

2. **Describe the Data Structure**: Explain entity relationships
   - "ACLs are in sys_security_acl table"
   - "Roles are linked to ACLs through sys_security_acl_role table"

3. **Highlight Performance Concerns**:
   - "The script needs to handle thousands of records efficiently"
   - "Use caching and limit queries where possible"

4. **Be Specific About Algorithms**:
   - "Check ACLs for mobile_admin role by directly querying the role assignments"
   - "Group ACLs by name before checking CRUD completeness"

5. **Provide Clear Success Criteria**:
   - "The script should clearly show what percentage of complete ACLs have the role"
   - "Highlight missing CRUD operations per ACL"

6. **For Iterations, Be Specific About Issues**:
   - "The summary is being generated before data processing is complete"
   - "Please move the summary to the top of the output with better formatting"

## Structured Development Approach for ServiceNow Scripts

For complex scripts, follow this approach:

1. **Requirement Analysis First**
   - Identify clear goals before starting to code

2. **Data Model Understanding**
   - Map out data relationships between tables
   - Understand how entities relate to each other

3. **Staged Development**
   - Build data collection first
   - Build analysis logic second
   - Build reporting last

4. **Use Output Buffering from the Start**
   - Separate data collection from output formatting
   - Collect all data before generating summary reports

5. **Optimize Performance Early**
   - Implement caching for frequently accessed data
   - Use query limits and filters appropriately
   - Minimize database calls

6. **Testing Strategy**
   - Test with small data samples first
   - Add debug output that can be toggled on/off
   - Verify key assumptions with debug output

By providing structured information upfront and following these development practices, you can arrive at effective solutions with fewer iterations.
