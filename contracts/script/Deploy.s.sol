// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {LandRegistryAnchor} from "../src/LandRegistryAnchor.sol";

contract Deploy is Script {
    function run() external returns (address) {
        uint256 pk = vm.envUint("REGISTRAR_PRIVATE_KEY");
        address admin = vm.addr(pk);
        vm.startBroadcast(pk);
        LandRegistryAnchor anchor = new LandRegistryAnchor(admin);
        vm.stopBroadcast();
        console.log("LandRegistryAnchor deployed at:", address(anchor));
        return address(anchor);
    }
}
