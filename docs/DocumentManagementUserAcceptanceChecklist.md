# Document Management — User Acceptance Testing Checklist

Use this checklist against the running Docker application after Milestone 2 technical closeout. Work from top to bottom and tick one item only after the behaviour has been observed successfully.

If a test fails, leave it unticked and record a short note or screenshot in the issue log at the end. Do not use real confidential documents during testing.

## Test record

- Tester: Wayne Townsend
- Date:
- openQMS commit/version:
- Browser/device:

## 1. Test setup

- [ ] Sign in as an administrator successfully.
- [ ] Confirm the Document Management section opens without an error.
- [ ] Confirm the document register is readable at normal desktop width.
- [ ] Confirm the document register remains usable at a narrow/mobile browser width.
- [ ] Create or identify a normal non-admin user for permission testing.
- [ ] Create or identify a person record that can be selected as a document owner.
- [ ] Prepare one PDF, one PNG or JPEG, one plain-text file, and one unsupported file type for upload testing.

## 2. Categories

- [ ] Create a top-level category.
- [ ] Create a child category beneath it.
- [ ] Create a second level of nesting beneath the child category.
- [ ] Rename a category and confirm the new name appears everywhere it is used.
- [ ] Move a child category to another valid parent.
- [ ] Move a child category back to the top level.
- [ ] Confirm a category cannot be made its own parent.
- [ ] Confirm a parent category cannot be moved beneath one of its descendants.
- [ ] Confirm cancelling a category edit leaves the original category unchanged.
- [ ] Delete an unused category and confirm it disappears.

## 3. Tags

- [ ] Create a tag.
- [ ] Create a second tag.
- [ ] Confirm both tags appear as document options.
- [ ] Delete an unused tag and confirm it disappears.
- [ ] Delete a tag that is assigned to a document and confirm the document remains available.

## 4. Creating and editing document records

- [ ] Create a document with the minimum required information.
- [ ] Confirm the document number is generated automatically.
- [ ] Confirm the generated document number is unique.
- [ ] Create a document with a category, owner, and multiple tags.
- [ ] Confirm the new document appears in the register.
- [ ] Open the document and confirm all saved metadata is correct.
- [ ] Change the document title and confirm the change persists after refreshing the page.
- [ ] Change the category and confirm the change persists.
- [ ] Change the owner and confirm the change persists.
- [ ] Add and remove tags and confirm the changes persist.
- [ ] Cancel a metadata edit and confirm no changes are saved.
- [ ] Confirm validation prevents saving incomplete or invalid required information.

## 5. Register, searching, filtering, and pagination

- [ ] Search for a document by full title.
- [ ] Search for a document by part of its title.
- [ ] Search for a document by full document number.
- [ ] Search for a document by part of its document number.
- [ ] Confirm a search with no matches shows a clear empty state.
- [ ] Filter documents by category.
- [ ] Filter documents by tag.
- [ ] Filter documents by owner.
- [ ] Filter documents by status.
- [ ] Combine two or more filters and confirm all results match every selected filter.
- [ ] Clear the filters and confirm the complete register returns.
- [ ] Change pages and confirm the expected documents are shown.
- [ ] Change the number of documents shown per page, if the control is available.
- [ ] Confirm search and filters still work after changing page.
- [ ] Confirm a newly created document can be found without reloading the application.

## 6. Version uploads

- [ ] Upload the first PDF version of a document.
- [ ] Confirm it is recorded as version 1 with the correct filename and change summary.
- [ ] Upload a second version and confirm it receives the next version number.
- [ ] Confirm the first version remains available and unchanged.
- [ ] Upload a PNG or JPEG version successfully.
- [ ] Upload a plain-text version successfully.
- [ ] Confirm an unsupported file type is rejected with a useful message.
- [ ] Confirm an empty or invalid upload is rejected cleanly.
- [ ] Cancel an upload and confirm no version is created.
- [ ] Refresh the page and confirm the complete version history remains present.

## 7. Preview and download

- [ ] Preview a PDF inside the application.
- [ ] Confirm the PDF preview cannot unexpectedly navigate or control the surrounding application.
- [ ] Close the PDF preview and confirm the document page remains usable.
- [ ] Preview a PNG or JPEG inside the application.
- [ ] Close the image preview and confirm the document page remains usable.
- [ ] Confirm a plain-text or unsupported preview type is refused clearly rather than displayed unsafely.
- [ ] Download the first version and confirm the correct file is received.
- [ ] Download a later version and confirm the correct file is received.
- [ ] Confirm the downloaded filename is sensible.
- [ ] Open and close previews repeatedly and confirm no obvious stale preview or browser slowdown occurs.

## 8. Approval and rejection workflow

- [ ] Submit a draft version for approval.
- [ ] Confirm the submitted version changes to In Review.
- [ ] Confirm an administrator can approve an In Review version.
- [ ] Confirm the approved version becomes the current published version.
- [ ] Confirm the document status becomes Approved after its first approval.
- [ ] Upload a new revision after approval and confirm the previously approved version remains current.
- [ ] Submit the new revision for approval and confirm the document still reflects the existing approved publication appropriately.
- [ ] Reject the new revision with a meaningful comment.
- [ ] Confirm a rejection comment is required.
- [ ] Confirm the rejection decision and comment appear in the history.
- [ ] Confirm rejecting a later revision does not remove or replace the previously approved version.
- [ ] Submit another revision and approve it.
- [ ] Confirm the newly approved revision becomes current.
- [ ] Confirm the earlier approved revision remains in the immutable history.
- [ ] Confirm invalid workflow actions are unavailable or produce a clear error.

## 9. Acknowledgements

- [ ] Acknowledge an approved document version as the signed-in user.
- [ ] Confirm the acknowledgement records the correct user and time.
- [ ] Acknowledge the same version again and confirm no duplicate acknowledgement is created.
- [ ] Sign in as the second user and acknowledge the same version.
- [ ] Confirm both users appear in the acknowledgement list.
- [ ] Confirm acknowledging one version does not falsely acknowledge a different version.

## 10. Version comparison

- [ ] Compare two different text-based versions.
- [ ] Confirm the comparison clearly identifies text added between versions.
- [ ] Confirm the comparison clearly identifies text removed between versions.
- [ ] Reverse the selected comparison order and confirm the result changes appropriately.
- [ ] Compare two binary/image/PDF versions and confirm an appropriate checksum or changed/not-changed result is shown.
- [ ] Compare two identical-content versions and confirm the result does not falsely report a content change.
- [ ] Close or reset the comparison and confirm the page returns to its normal state.

## 11. Retirement and deletion

- [ ] Retire an approved document as an administrator.
- [ ] Confirm the document status becomes Obsolete.
- [ ] Confirm the complete version and approval history remains available after retirement.
- [ ] Confirm an ordinary submit or rejection action cannot silently reactivate an obsolete document.
- [ ] Confirm any deliberate reactivation route behaves as clearly described by the interface.
- [ ] Soft-delete a disposable test document as an administrator.
- [ ] Confirm the deleted document no longer appears in the normal register.
- [ ] Confirm deleting one document does not affect unrelated documents.

## 12. Normal-user permissions

- [ ] Sign out of the administrator account and sign in as the normal user.
- [ ] Confirm the normal user can view the document register.
- [ ] Confirm the normal user can open document details and version history.
- [ ] Confirm the normal user can search and filter documents.
- [ ] Confirm the normal user can preview and download permitted files.
- [ ] Confirm the normal user can create and edit document metadata as currently intended.
- [ ] Confirm the normal user can upload a new version as currently intended.
- [ ] Confirm the normal user can submit a draft version for approval.
- [ ] Confirm the normal user cannot approve a version.
- [ ] Confirm the normal user cannot reject a version.
- [ ] Confirm the normal user cannot retire a document.
- [ ] Confirm the normal user cannot soft-delete a document.
- [ ] Confirm the normal user cannot create, edit, move, or delete categories.
- [ ] Confirm the normal user cannot create or delete tags.
- [ ] Confirm manually navigating to an admin-only action does not bypass server permissions.

## 13. Session, refresh, and stale-state checks

- [ ] Refresh the browser while viewing a document and confirm the correct document reloads.
- [ ] Move quickly between two document detail pages and confirm information from one never appears on the other.
- [ ] Change filters quickly and confirm an older response does not overwrite the newest results.
- [ ] Open two browser tabs on the same document and make a safe test change in one tab.
- [ ] Refresh the second tab and confirm it displays the latest saved state.
- [ ] Sign out and confirm protected document pages are no longer accessible.
- [ ] Sign back in and confirm document data is still present.
- [ ] Restart the openQMS Docker application and confirm documents, versions, files, approvals, and acknowledgements persist.

## 14. General usability review

- [ ] Confirm all buttons and actions use terminology that makes sense to a quality professional.
- [ ] Confirm destructive actions ask for appropriate confirmation.
- [ ] Confirm success messages clearly state what changed.
- [ ] Confirm error messages explain what failed without exposing technical secrets.
- [ ] Confirm loading states make it clear when the application is working.
- [ ] Confirm empty states explain what the user can do next.
- [ ] Confirm keyboard navigation reaches the main controls in a sensible order.
- [ ] Confirm visible focus indicators make keyboard position clear.
- [ ] Confirm labels, status colours, and icons remain understandable without relying on colour alone.
- [ ] Confirm long titles, filenames, category names, tag names, and comments remain readable without breaking the layout.
- [ ] Confirm the complete Document Management workflow feels practical for real controlled-document work.

## Issue log

Record only failed, confusing, or questionable items here. Use the checklist wording as the issue title so it can be traced easily.

- Issue:
  - What happened:
  - What was expected:
  - Document/version used:
  - Browser/device:
  - Screenshot or error text:

- Issue:
  - What happened:
  - What was expected:
  - Document/version used:
  - Browser/device:
  - Screenshot or error text:
