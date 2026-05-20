// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {LandRegistryAnchor} from "../src/LandRegistryAnchor.sol";
import {MultiSigRegistrar} from "../src/MultiSigRegistrar.sol";

contract MultiSigRegistrarTest is Test {
    LandRegistryAnchor public anchor;
    MultiSigRegistrar public sig;

    address[] public signers;
    address public outsider = address(0xDEAD);

    function setUp() public {
        signers.push(address(0xA1)); // MoLHUD Commissioner
        signers.push(address(0xA2)); // NITA-U Security
        signers.push(address(0xA3)); // District Land Board
        signers.push(address(0xA4)); // LandGuard project
        signers.push(address(0xA5)); // Independent auditor
        anchor = new LandRegistryAnchor(address(this));
        sig = new MultiSigRegistrar(signers, 3, address(anchor));
        // Hand REGISTRAR_ROLE on the anchor to the multisig only.
        anchor.grantRole(anchor.REGISTRAR_ROLE(), address(sig));
        anchor.revokeRole(anchor.REGISTRAR_ROLE(), address(this));
    }

    function test_ThreeOfFiveCommits() public {
        uint16 d = 3;
        bytes32 batch = keccak256("batch-1");
        bytes32 root = keccak256("root-1");

        vm.prank(signers[0]);
        sig.proposeAndConfirm(d, batch, root);
        vm.prank(signers[1]);
        sig.proposeAndConfirm(d, batch, root);
        // Not yet executed — only 2 confirmations.
        (, , , uint8 confirmations, bool executed, ) = sig.proposals(sig.proposalIdOf(d, batch, root));
        assertEq(confirmations, 2);
        assertFalse(executed);

        vm.prank(signers[2]);
        sig.proposeAndConfirm(d, batch, root);
        (, , , confirmations, executed, ) = sig.proposals(sig.proposalIdOf(d, batch, root));
        assertEq(confirmations, 3);
        assertTrue(executed);

        // Confirm by reading the anchor directly.
        (bytes32 storedRoot, uint16 storedDistrict, , ) = anchor.anchors(batch);
        assertEq(storedRoot, root);
        assertEq(storedDistrict, d);
    }

    function test_NonSignerRejected() public {
        vm.prank(outsider);
        vm.expectRevert(MultiSigRegistrar.NotASigner.selector);
        sig.proposeAndConfirm(1, keccak256("b"), keccak256("r"));
    }

    function test_DoubleConfirmRejected() public {
        bytes32 batch = keccak256("dup");
        bytes32 root = keccak256("r");
        vm.startPrank(signers[0]);
        sig.proposeAndConfirm(1, batch, root);
        vm.expectRevert(MultiSigRegistrar.AlreadyConfirmed.selector);
        sig.proposeAndConfirm(1, batch, root);
        vm.stopPrank();
    }

    function test_PostExecutionConfirmRejected() public {
        bytes32 batch = keccak256("done");
        bytes32 root = keccak256("r");
        vm.prank(signers[0]);
        sig.proposeAndConfirm(1, batch, root);
        vm.prank(signers[1]);
        sig.proposeAndConfirm(1, batch, root);
        vm.prank(signers[2]);
        sig.proposeAndConfirm(1, batch, root); // executes
        vm.prank(signers[3]);
        vm.expectRevert(MultiSigRegistrar.AlreadyExecuted.selector);
        sig.proposeAndConfirm(1, batch, root);
    }

    function test_DirectAnchorBypassFails() public {
        // The deployer no longer has REGISTRAR_ROLE; only the multisig does.
        vm.expectRevert();
        anchor.commitBatch(1, keccak256("b"), keccak256("r"));
    }
}
