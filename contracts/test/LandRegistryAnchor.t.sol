// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {LandRegistryAnchor} from "../src/LandRegistryAnchor.sol";
import {IAccessControl} from "@openzeppelin/contracts/access/IAccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

contract LandRegistryAnchorTest is Test {
    LandRegistryAnchor public anchor;
    address public admin = address(0xA11CE);
    address public other = address(0xB0B);

    function setUp() public {
        anchor = new LandRegistryAnchor(admin);
    }

    function test_CommitBatch_HappyPath() public {
        bytes32 batchId = keccak256("batch-1");
        bytes32 root = keccak256("root-1");
        vm.prank(admin);
        anchor.commitBatch(3, batchId, root);
        (bytes32 storedRoot, uint16 d, uint64 ts, address registrar) = anchor.anchors(batchId);
        assertEq(storedRoot, root);
        assertEq(d, 3);
        assertGt(ts, 0);
        assertEq(registrar, admin);
        assertEq(anchor.totalAnchors(), 1);
    }

    function test_CommitBatch_RejectsDuplicate() public {
        bytes32 batchId = keccak256("dup");
        bytes32 root = keccak256("any");
        vm.startPrank(admin);
        anchor.commitBatch(1, batchId, root);
        vm.expectRevert(abi.encodeWithSelector(LandRegistryAnchor.DuplicateBatch.selector, batchId));
        anchor.commitBatch(1, batchId, root);
        vm.stopPrank();
    }

    function test_CommitBatch_RejectsEmptyRoot() public {
        vm.prank(admin);
        vm.expectRevert(LandRegistryAnchor.EmptyRoot.selector);
        anchor.commitBatch(1, keccak256("b"), bytes32(0));
    }

    function test_CommitBatch_NonRegistrarReverts() public {
        // Precompute the role hash OUTSIDE the prank — the view call would
        // otherwise consume vm.prank's single-call effect.
        bytes32 role = anchor.REGISTRAR_ROLE();
        vm.expectRevert(
            abi.encodeWithSelector(
                IAccessControl.AccessControlUnauthorizedAccount.selector,
                other,
                role
            )
        );
        vm.prank(other);
        anchor.commitBatch(1, keccak256("b"), keccak256("r"));
    }

    function test_Pause_BlocksCommits() public {
        vm.prank(admin);
        anchor.pause();
        vm.prank(admin);
        vm.expectRevert(Pausable.EnforcedPause.selector);
        anchor.commitBatch(1, keccak256("b"), keccak256("r"));
        vm.prank(admin);
        anchor.unpause();
        vm.prank(admin);
        anchor.commitBatch(1, keccak256("b"), keccak256("r"));
    }

    /// @dev Test vector cross-checks with backend audit/merkle.py — same leaves, same root.
    function test_VerifyProof_ThreeLeaves() public {
        bytes32 leafA = keccak256("alpha");
        bytes32 leafB = keccak256("beta");
        bytes32 leafC = keccak256("gamma");
        // Pair (a,b) using sorted concat, then duplicate-last for odd levels.
        bytes32 ab = _hashPair(leafA, leafB);
        bytes32 cc = _hashPair(leafC, leafC);
        bytes32 root = _hashPair(ab, cc);

        bytes32 batchId = keccak256("verify-batch");
        vm.prank(admin);
        anchor.commitBatch(2, batchId, root);

        // Proof for leafA: sibling=B at level 0, sibling=cc at level 1.
        bytes32[] memory proof = new bytes32[](2);
        proof[0] = leafB;
        proof[1] = cc;
        assertTrue(anchor.verifyProof(batchId, leafA, proof));
        // Tampered leaf must fail.
        assertFalse(anchor.verifyProof(batchId, keccak256("tampered"), proof));
    }

    function test_VerifyProof_UnknownBatch() public view {
        bytes32[] memory proof = new bytes32[](0);
        assertFalse(anchor.verifyProof(keccak256("nope"), keccak256("x"), proof));
    }

    function _hashPair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a <= b
            ? keccak256(abi.encodePacked(a, b))
            : keccak256(abi.encodePacked(b, a));
    }
}
