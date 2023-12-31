from pathlib import Path
from beaker import *
from typing import Literal
from beaker.lib.storage import BoxMapping
from pyteal import *


class NFTticket(abi.NamedTuple):
    name: abi.Field[abi.String]
    total: abi.Field[abi.Uint64]
    asset_url: abi.Field[abi.String]
    asset_price: abi.Field[abi.Uint64]
    organizer_address: abi.Field[abi.Address]


class Dapp:
    # Box Storage
    minted_tickets = BoxMapping(
        key_type=abi.Tuple2[abi.Address, abi.Uint64],
        value_type=NFTticket,
        prefix=Bytes("m-"),
    )
    points = BoxMapping(
        key_type=abi.Address,
        value_type=abi.Uint64,
        prefix=Bytes("p-"),
    )


app = Application("NFTticketingdApp", state=Dapp)


@app.create(bare=True)
def create() -> Expr:
    return app.initialize_global_state()


@app.external
def mint(
    ticket: NFTticket,
    ticket_id: abi.Uint64,
    mbr_payment: abi.PaymentTransaction,
    *,
    output: abi.Uint64,
) -> Expr:
    ticket_key = abi.make(abi.Tuple2[abi.Address, abi.Uint64])
    addr = abi.Address()
    name = abi.String()
    total = abi.Uint64()
    asset_url = abi.String()
    asset_price = abi.Uint64()
    organizer_address = abi.Address()
    return Seq(
        # Assert MBR payment is going to the contract
        Assert(mbr_payment.get().receiver() == Global.current_application_address()),
        # Get current MBR before adding nfttickets
        pre_mbr := AccountParam.minBalance(Global.current_application_address()),
        # Set ticket key
        addr.set(Global.current_application_address()),
        ticket_key.set(addr, ticket_id),
        # Check if the ticket already exists
        Assert(app.state.minted_tickets[ticket_key].exists() == Int(0)),
        app.state.minted_tickets[ticket_key].set(ticket),
        # Get properties from ticket and mint NFT
        ticket.name.store_into(name),
        ticket.total.store_into(total),
        ticket.asset_url.store_into(asset_url),
        ticket.asset_price.store_into(asset_price),
        ticket.organizer_address.store_into(organizer_address),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: name.get(),
                TxnField.config_asset_unit_name: Bytes("TNFT"),
                TxnField.config_asset_reserve: Global.current_application_address(),
                TxnField.config_asset_url: asset_url.get(),
                TxnField.config_asset_total: total.get(),
                TxnField.fee: Int(0),
            }
        ),
        # Verify payment covers MBR difference
        current_mbr := AccountParam.minBalance(Global.current_application_address()),
        Assert(mbr_payment.get().amount() >= current_mbr.value() - pre_mbr.value()),
        output.set(InnerTxn.created_asset_id()),
    )


@app.external
def buy(
    asset: abi.Asset,
    ticket_id: abi.Uint64,
    payment: abi.PaymentTransaction,
    optin_payment: abi.AssetTransferTransaction,
) -> Expr:
    return_value = NFTticket()
    asset_price = abi.Uint64()
    organizer_address = abi.Address()
    ticket_key = abi.make(abi.Tuple2[abi.Address, abi.Uint64])
    addr1 = abi.Address()
    points = abi.Uint64()
    return Seq(
        # Set ticket key
        addr1.set(Global.current_application_address()),
        ticket_key.set(addr1, ticket_id),
        # Store the value boxmapping[index]
        app.state.minted_tickets[ticket_key].store_into(return_value),
        return_value.asset_price.store_into(asset_price),
        return_value.organizer_address.store_into(organizer_address),
        # Verify payment transaction
        Assert(payment.get().amount() == (asset_price.get())),
        Assert(payment.get().receiver() == organizer_address.get()),
        If(app.state.points[Txn.sender()].exists())
        .Then(
            app.state.points[Txn.sender()].store_into(points),
            app.state.points[Txn.sender()].set(Itob(points.get() + Int(1))),
        )
        .Else(app.state.points[Txn.sender()].set(Itob(Int(1)))),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.fee: Int(0),  # cover fee with outer txn
                TxnField.asset_receiver: Txn.sender(),
                TxnField.xfer_asset: asset.asset_id(),
                TxnField.asset_amount: Int(1),
            }
        ),
    )


@app.external
def buyforpoints(
    asset: abi.Asset,
    optin_payment: abi.AssetTransferTransaction,
) -> Expr:
    points = abi.Uint64()
    return Seq(
        # Store it into points
        app.state.points[Txn.sender()].store_into(points),
        # Add a point to the buyer
        app.state.points[Txn.sender()].set(Itob(points.get() - Int(1))),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.fee: Int(0),  # cover fee with outer txn
                TxnField.asset_receiver: Txn.sender(),
                TxnField.xfer_asset: asset.asset_id(),
                TxnField.asset_amount: Int(1),
            }
        ),
    )


if __name__ == "__main__":
    app.build().export(Path(__file__).resolve().parent / "./artifacts")
