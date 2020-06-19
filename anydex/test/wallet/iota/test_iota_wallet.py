from iota import Address, Transaction, Bundle
from iota.crypto.types import Seed
from ipv8.util import succeed
from sqlalchemy.orm import session as db_session

from anydex.test.base import AbstractServer
from anydex.wallet.iota.iota_database import DatabaseBundle, DatabaseAddress, DatabaseTransaction, DatabaseSeed
from anydex.wallet.iota.iota_provider import PyOTAIotaProvider
from anydex.wallet.iota.iota_wallet import IotaWallet, IotaTestnetWallet
from anydex.wallet.wallet import InsufficientFunds


class TestIotaWallet(AbstractServer):

    tx1 = Transaction.from_tryte_string(
        'PCGDSCPCSCGD9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '999999999999999999999999999999999999999999999999999999999999999999999999999999999999999VETULPZOCVDRE'
        'KATOFLERUIOSIIG9XTCMMVTDPFFPSDXXPMLRAZXUBLLRMTEWJZPBNJBAMFCJQDSWPTV9OB9999999999999999999999999EINFA'
        'CHIOTA9999999999999999999999999999999999C99999999NXPJH9TJ99PQGWXYAJKDTNHBWPJURJTIIYSNZH9EUYTDJGAICWT'
        'E9LC9KPLVTLIDSJSGRGWAUBFPAPKXAFIFEQNHUHEJNRBARNJYEEVIUPZXMTLTWGOBDLKMGOV9ISJMYPWLMHMXZLQKUMNBIFBEAUJ'
        'W9CBERPC999JNOBIMVGJEHXXTMMEDOEJFYKIMEFGA9MAITXIBCPCDJSDPMKXFSXRIMBDHUFEYOV9GWAQVXEHWLKMZ999EINFACHI'
        'OTA9999999999999999999999999999999999999999999EX99999999CCA99999999999999')
    tx2 = Transaction.from_tryte_string(
        'GYPRVHBEZOOFXSHQBLCYW9ICTCISLHDBNMMVYD9JJHQMPQCTIQAQTJNNNJ9IDXLRCCOYOXYPCLR9PBEY9ORZIEPPDNTI9CQWYZUO'
        'TAVBXPSBOFEQAPFLWXSWUIUSJMSJIIIZWIKIRH9GCOEVZFKNXEVCUCIIWZQCQEUVRZOCMEL9AMGXJNMLJCIA9UWGRPPHCEOPTSVP'
        'KPPPCMQXYBHMSODTWUOABPKWFFFQJHCBVYXLHEWPD9YUDFTGNCYAKQKVEZYRBQRBXIAUX9SVEDUKGMTWQIYXRGSWYRK9SRONVGTW'
        '9YGHSZRIXWGPCCUCDRMAXBPDFVHSRYWHGB9DQSQFQKSNICGPIPTRZINYRXQAFSWSEWIFRMSBMGTNYPRWFSOIIWWT9IDSELM9JUOO'
        'WFNCCSHUSMGNROBFJX9JQ9XT9PKEGQYQAWAFPRVRRVQPUQBHLSNTEFCDKBWRCDX9EYOBB9KPMTLNNQLADBDLZPRVBCKVCYQEOLAR'
        'JYAGTBFR9QLPKZBOYWZQOVKCVYRGYI9ZEFIQRKYXLJBZJDBJDJVQZCGYQMROVHNDBLGNLQODPUXFNTADDVYNZJUVPGB9LVPJIYLA'
        'PBOEHPMRWUIAJXVQOEM9ROEYUOTNLXVVQEYRQWDTQGDLEYFIYNDPRAIXOZEBCS9P99AZTQQLKEILEVXMSHBIDHLXKUOMMNFKPYHO'
        'NKEYDCHMUNTTNRYVMMEYHPGASPZXASKRUPWQSHDMU9VPS99ZZ9SJJYFUJFFMFORBYDILBXCAVJDPDFHTTTIYOVGLRDYRTKHXJORJ'
        'VYRPTDH9ZCPZ9ZADXZFRSFPIQKWLBRNTWJHXTOAUOL9FVGTUMMPYGYICJDXMOESEVDJWLMCVTJLPIEKBE9JTHDQWV9MRMEWFLPWG'
        'JFLUXI9BXPSVWCMUWLZSEWHBDZKXOLYNOZAPOYLQVZAQMOHGTTQEUAOVKVRRGAHNGPUEKHFVPVCOYSJAWHZU9DRROHBETBAFTATV'
        'AUGOEGCAYUXACLSSHHVYDHMDGJP9AUCLWLNTFEVGQGHQXSKEMVOVSKQEEWHWZUDTYOBGCURRZSJZLFVQQAAYQO9TRLFFN9HTDQX'
        'SPPJYXMNGLLBHOMNVXNOWEIDMJVCLLDFHBDONQJCJVLBLCSMDOUQCKKCQJMGTSTHBXPXAMLMSXRIPUBMBAWBFNLHLUJTRJLDERLZ'
        'FUBUSMF999XNHLEEXEENQJNOFFPNPQ9PQICHSATPLZVMVIWLRTKYPIXNFGYWOJSQDAXGFHKZPFLPXQEHCYEAGTIWIJEZTAVLNUMA'
        'FWGGLXMBNUQTOFCNLJTCDMWVVZGVBSEBCPFSM99FLOIDTCLUGPSEDLOKZUAEVBLWNMODGZBWOVQT9DPFOTSKRABQAVOQ9RXWBMAK'
        'FYNDCZOJGTCIDMQSQQSODKDXTPFLNOKSIZEOY9HFUTLQRXQMEPGOXQGLLPNSXAUCYPGZMNWMQWSWCKAQYKXJTWINSGPPZG9HLDLE'
        'AWUWEVCTVRCBDFOXKUROXH9HXXAXVPEJFRSLOGRVGYZASTEBAQNXJJROCYRTDPYFUIQJVDHAKEG9YACV9HCPJUEUKOYFNWDXCCJ'
        'IFQKYOXGRDHVTHEQUMHO99999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999'
        '9999999999999999999999RKWEEVD99A99999999A99999999NFDPEEZCWVYLKZGSLCQNOFUSENIXRHWWTZFBXMPSQHEDFWZULBZ'
        'FEOMNLRNIDQKDNNIELAOXOVMYEI9PGTKORV9IKTJZQUBQAWTKBKZ9NEZHBFIMCLV9TTNJNQZUIJDFPTTCTKBJRHAITVSKUCUEMD9'
        'M9SQJ999999TKORV9IKTJZQUBQAWTKBKZ9NEZHBFIMCLV9TTNJNQZUIJDFPTTCTKBJRHAITVSKUCUEMD9M9SQJ99999999999999'
        '9999999999999999999999999999999999999999999999999999999999999999999999999'
    )

    def setUp(self):
        super(TestIotaWallet, self).setUp()
        self.wallet = self.new_wallet()
        self.identifier = 'IOTA'
        self.name = 'iota'
        self.testnet = False

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def new_wallet(self):
        return IotaWallet(self.session_base_dir)

    def test_min_unit(self):
        """
        Test the min_unit function
        """
        result = self.wallet.min_unit()
        self.assertEqual(0, result)
        self.wallet.cancel_all_pending_tasks()

    def test_is_testnet(self):
        """
        Test the is_testnet function
        """
        result = self.wallet.testnet
        self.assertEqual(self.testnet, result)
        self.wallet.cancel_all_pending_tasks()

    def test_get_name(self):
        """
        Test for get_name
        """
        result = self.wallet.get_name()
        self.assertEqual(self.name, result)
        self.wallet.cancel_all_pending_tasks()

    def test_get_identifier(self):
        """
        Test for get identifier
        """
        result = self.wallet.get_identifier()
        self.assertEqual(self.identifier, result)
        self.wallet.cancel_all_pending_tasks()

    def test_create_wallet(self):
        """
        Test wallet creation and side effects
        """
        # Check that wallet is not automatically created
        self.assertFalse(self.wallet.created)
        # Create the wallet
        self.wallet.create_wallet()
        # Check that all initializations occurred correctly
        self.assertTrue(self.wallet.created)
        self.assertIsNotNone(self.wallet.seed)
        self.assertIsNotNone(self.wallet.provider)
        self.wallet.cancel_all_pending_tasks()

    def test_erroneous_wallet_creation(self):
        """
        Tests creating an already created wallet
        """
        self.wallet.create_wallet()  # Create the wallet once
        response = self.wallet.create_wallet()
        # Check that an exception is returned when a wallet is created again
        self.assertIsInstance(response.exception(), RuntimeError)
        # Check that the second wallet creation did not damage the first
        self.assertTrue(self.wallet.created)
        self.assertIsNotNone(self.wallet.seed)
        self.assertIsNotNone(self.wallet.provider)
        self.wallet.cancel_all_pending_tasks()

    def test_double_wallet_instantiation(self):
        """
        Tests that parameters of two wallets with the same name
        Are identical.
        """
        # Create a wallet
        self.wallet.create_wallet()
        # Instantiate another wallet, without creating it
        new_wallet = self.new_wallet()
        # Assert equality of name and seed
        self.assertEqual(self.wallet.wallet_name, new_wallet.wallet_name)
        self.assertEqual(self.wallet.seed, new_wallet.seed)
        self.wallet.cancel_all_pending_tasks()

    def test_wallet_exists(self):
        """
        Tests the good and bad weather cases of wallet_exist
        """
        # Wallet is instantiated, but not created
        self.assertFalse(self.wallet.wallet_exists())
        # Create the wallet
        self.wallet.create_wallet()
        # Check that the creation is correctly identified
        self.assertTrue(self.wallet.wallet_exists())
        self.wallet.cancel_all_pending_tasks()

    async def test_get_address_before_creation(self):
        """
        Bad weather test case for getting an address
        """
        # Get the address
        result = await self.wallet.get_address()
        # Assert the type and content
        self.assertEqual('', result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_address_correct(self):
        """
        Tests the generation of a fresh address, when no others exist
        """
        address_length = 81
        address = 'ZLGVEQ9JUZZWCZXLWVNTHBDX9G9KZTJP9VEERIIFHY9SIQKYBVAHIMLHXPQVE9IXFDDXNHQINXJDRPFDX'

        # Create the wallet
        self.wallet.create_wallet()

        # Get the address
        self.wallet.provider.generate_address = lambda index: succeed(Address(address))
        result = await self.wallet.get_address()

        addresses_after = self.wallet.database.query(DatabaseAddress) \
            .filter(DatabaseAddress.seed.__eq__(self.wallet.seed.__str__())) \
            .all()

        # Assert the type and length
        self.assertIsNotNone(result)
        self.assertEqual(address_length, len(result))
        # Assert correct result and storage
        self.assertEqual(address, addresses_after[0].address)
        self.assertEqual(1, len(addresses_after))
        self.wallet.cancel_all_pending_tasks()

    async def test_get_address_all_spent(self):
        """
        Tests getting a new address when all current addresses are spent
        """
        address_length = 81
        old_address = 'ZLGVEQ9JUZZWCZXLWVNTHBDX9G9KZTJP9VEERIIFHY9SIQKYBVAHIMLHXPQVE9IXFDDXNHQINXJDRPFDXNYVAPLZAW'

        # Create the wallet
        self.wallet.create_wallet()
        # Add an unspent address to the database
        self.wallet.database.add(DatabaseAddress(
            address=old_address,
            is_spent=False
        ))
        # Mock the api call
        self.wallet.provider.is_spent = lambda address: succeed(True)
        self.wallet.provider.generate_address = lambda index: \
            succeed(Address('JREQJMOEACYWASLKKVDWQHXHGTWAEFOXMGNSYEWZ9VIKSEJKRVSCSRN9IDEBMK9SKODVLPTPNHBKBN9LY'))
        result = await self.wallet.get_address()
        # Assert the type and length
        self.assertEqual(address_length, len(result))
        # Check correct database storage of the new address
        non_spent = self.wallet.database.query(DatabaseAddress) \
            .filter(DatabaseAddress.seed.__eq__(self.wallet.seed.__str__())) \
            .first()
        previous = self.wallet.database.query(DatabaseAddress) \
            .filter(DatabaseAddress.address.__eq__(old_address)) \
            .first()
        # Check if the new address is unspent
        self.assertEqual(False, non_spent.is_spent)
        # Check if the old address has been correctly updated
        self.assertEqual(True, previous.is_spent)
        self.wallet.cancel_all_pending_tasks()

    async def test_transfer_before_creation(self):
        """
        Tests the bad weather case of transferring before wallet creation.
        """
        # Address taken from IOTA documentation.
        to_address = 'ZLGVEQ9JUZZWCZXLWVNTHBDX9G9KZTJP9VEERIIFHY9SIQKYBVAHIMLHXPQVE9IXFDDXNHQINXJDRPFDXNYVAPLZAW'
        # Try sending a transfer
        result = await self.wallet.transfer(0, to_address)
        # Assert tpye and contents.
        self.assertIsInstance(result, RuntimeError)
        self.wallet.cancel_all_pending_tasks()

    async def test_transfer_insufficient_funds(self):
        """
        Tests the transfer when the balance of the wallet is insufficient
        """
        self.wallet.create_wallet()
        # Address taken from IOTA documentation.
        to_address = 'ZLGVEQ9JUZZWCZXLWVNTHBDX9G9KZTJP9VEERIIFHY9SIQKYBVAHIMLHXPQVE9IXFDDXNHQINXJDRPFDXNYVAPLZAW'

        # Set up mocks.
        self.wallet.get_balance = lambda: \
            succeed({'available': 0, 'pending': 0, 'currency': self.identifier, 'precision': 0})
        # Try sending a transfer with a value higher than the
        # Available amount.
        result = await self.wallet.transfer(1, to_address)
        # Assert type and contents.
        self.assertIsInstance(result, InsufficientFunds)
        self.wallet.cancel_all_pending_tasks()

    async def test_transfer_negative_amount(self):
        """
        Test the transfer of a negative amount of IOTA
        """
        self.wallet.create_wallet()
        # Address taken from IOTA documentation.
        to_address = 'ZLGVEQ9JUZZWCZXLWVNTHBDX9G9KZTJP9VEERIIFHY9SIQKYBVAHIMLHXPQVE9IXFDDXNHQINXJDRPFDXNYVAPLZAW'
        self.wallet.get_balance = lambda: \
            succeed({'available': 42, 'pending': 0, 'currency': self.identifier, 'precision': 6})
        # Try sending the invalid amount
        result = await self.wallet.transfer(-1, to_address)
        # Assert type and contents.
        self.assertIsInstance(result, RuntimeError)
        self.wallet.cancel_all_pending_tasks()

    async def test_transfer_invalid_address(self):
        """
        Test the transfer to an invalid IOTA address
        """
        self.wallet.create_wallet()
        # Address contains a random lower case letter
        to_address = 'ZLGVEQ9JUZZWCZXLWVaTHBDX9G9KZTJP9VEERIIFHY9SIQKYBVAHIMLHXPQVE9IXFDDXNHQINXJDRPFDXNYVAPLZAW'
        self.wallet.get_balance = lambda: \
            succeed({'available': 42, 'pending': 0, 'currency': self.identifier, 'precision': 0})
        # Try sending the invalid amount
        result = await self.wallet.transfer(0, to_address)
        # Assert type and contents.
        self.assertIsInstance(result, RuntimeError)
        self.wallet.cancel_all_pending_tasks()

    async def test_correct_transfer(self):
        """
        Tests the good weather case for transfers
        """
        bundle = Bundle([self.tx2])
        self.wallet.create_wallet()

        # Set up mocks.
        self.wallet.get_balance = lambda: \
            succeed({'available': 42, 'pending': 0, 'currency': self.identifier, 'precision': 0})
        self.wallet.provider.submit_transaction = lambda transaction: succeed(bundle)
        self.wallet.provider.get_all_bundles = lambda: succeed([bundle])
        self.wallet.provider.get_seed_transactions = lambda: succeed([self.tx2])
        # Send a correct transfer
        result = await self.wallet.transfer(1, self.tx2.address.__str__())
        # Update the database
        await self.wallet.update_transactions_database()
        await self.wallet.update_bundles_database()
        # Check correct bundle storage
        all_bundles = self.wallet.database.query(DatabaseBundle) \
            .all()
        # Get the bundle sent in the transaction
        bundle_query = self.wallet.database.query(DatabaseBundle) \
            .filter(DatabaseBundle.hash.__eq__(bundle.hash.__str__())) \
            .all()
        self.assertEqual(len(all_bundles), 1)
        self.assertEqual(bundle_query, all_bundles)

        # Check correct transaction storage
        all_txs = self.wallet.database.query(DatabaseTransaction) \
            .all()
        # Get the transaction that's part of the bundle
        tx_query = self.wallet.database.query(DatabaseTransaction) \
            .filter(DatabaseTransaction.hash.__eq__(self.tx2.hash.__str__())) \
            .all()
        self.assertEqual(len(all_txs), 1)
        self.assertEqual(all_txs, tx_query)

        # Assert correct return value
        self.assertEqual(bundle.hash.__str__(), result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_balance_before_creation(self):
        """
        Tests getting a balance before a wallet is created
        """
        expected = {
            'available': 0,
            'pending': 0,
            'currency': self.identifier,
            'precision': 0
        }
        # Get the balance of the uncreated wallet
        result = await self.wallet.get_balance()
        self.assertDictEqual(expected, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_balance_correct(self):
        """
        Tests getting a balance before a wallet is created
        """
        self.wallet.create_wallet()
        expected = {
            'available': 42,
            'pending': 0,
            'currency': self.identifier,
            'precision': 0
        }

        # Set up other wallet variables
        self.wallet.get_pending = lambda: succeed(0)
        self.wallet.provider.get_seed_balance = lambda: succeed(42)
        self.wallet.provider.get_seed_transactions = lambda: succeed(None)
        self.wallet.update_bundles_database = lambda: succeed({'transactions': []})
        self.wallet.update_transactions_database = lambda: succeed(None)
        # Get the balance of the uncreated wallet
        result = await self.wallet.get_balance()
        self.assertDictEqual(expected, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_pending_before_creation(self):
        """
        Tests the pending balance of an uncreated wallet
        """
        result = await self.wallet.get_pending()
        self.assertEqual(0, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_pending_no_transactions(self):
        """
        Tests the pending balance with no transactions
        """
        self.wallet.create_wallet()

        self.wallet.provider.get_seed_transactions = lambda: succeed([])
        self.wallet.update_bundles_database = lambda: succeed(None)
        result = await self.wallet.get_pending()
        self.assertEqual(0, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_pending_confirmed_transaction(self):
        """
        Tests the pending balance with one confirmed transaction
        """
        self.wallet.create_wallet()
        # Inject the valued transaction
        self.tx1.is_confirmed = True

        self.wallet.update_bundles_database = lambda: succeed(None)
        self.wallet.provider.get_seed_transactions = lambda: succeed([self.tx1])
        result = await self.wallet.get_pending()
        # Since the transaction is confirmed, no value should be added
        self.assertEqual(0, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_pending_multiple(self):
        """
        Tests the pending balance with no transactions
        """
        self.wallet.create_wallet()
        # Inject the valued transaction
        self.tx1.is_confirmed = False
        self.tx2.is_confirmed = False
        self.tx2.value = 1

        self.wallet.provider.get_seed_transactions = lambda: succeed([self.tx1, self.tx2])
        await self.wallet.update_transactions_database()

        result = await self.wallet.get_pending()
        # Since the transaction is confirmed, no value should be added
        self.assertEqual(self.tx2.value + self.tx1.value, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_transactions_before_creation(self):
        """
        Tests the get transaction method for a wallet not yet created
        """
        result = await self.wallet.get_transactions()
        expected = []
        self.assertEqual(expected, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_transactions_zero_transactions(self):
        """
        Tests the get transaction method no transactions
        """
        self.wallet.create_wallet()

        async def get_tx_mock():
            return []

        self.wallet.provider.get_seed_transactions = get_tx_mock
        self.wallet.update_bundles_database = lambda: succeed([])
        result = await self.wallet.get_transactions()
        expected = []
        self.assertEqual(expected, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_get_transactions_one_transaction(self):
        """
        Tests the get_transactions method for one transaction
        """
        # Circumvent wallet creation in order to control the seed
        self.wallet.seed = Seed('WKRHZILTMDEHELZCVZJSHWTLVGZBVDHEQQMG9LENEOMVRWGTJLSNWAMNF9HMPRTMGIONXXNDHUNRENDPX')
        self.wallet.created = True

        # Instantiate API
        self.wallet.provider = PyOTAIotaProvider(testnet=self.wallet.testnet, seed=self.wallet.seed)
        # Mock the API call return
        self.wallet.provider.get_seed_transactions = lambda: succeed([self.tx1])
        self.wallet.update_bundles_database = lambda: succeed(None)
        # Add the seed and the bundle to the database
        self.wallet.database.add(DatabaseSeed(name=self.wallet.wallet_name, seed=self.wallet.seed.__str__()))
        self.wallet.database.add(DatabaseBundle(hash=self.tx1.bundle_hash.__str__()))
        # Commit changes
        self.wallet.database.commit()
        # Call the tested function
        result = await self.wallet.get_transactions()
        # Construct expected response based on the values of tx1
        expected = [{
            'hash': self.tx1.hash.__str__(),
            'outgoing': False,
            'address': self.tx1.address.__str__(),
            'amount': self.tx1.value,
            'currency': self.identifier,
            'timestamp': self.tx1.timestamp,
            'bundle': self.tx1.bundle_hash.__str__(),
            'is_confirmed': False
        }]
        self.assertEqual(expected, result)
        self.wallet.cancel_all_pending_tasks()

    async def test_bundle_updates_change_one_bundle(self):
        """
        Tests updating the confirmation value of a bundle
        """
        self.wallet.create_wallet()
        bundle = Bundle([self.tx1])
        # Make sure the bundle is confirmed
        bundle.is_confirmed = True
        # Create DatabaseBundle based on tx1
        database_bundle = DatabaseBundle(
            hash=bundle.hash.__str__(),
            tail_transaction_hash=self.tx1.hash.__str__(),
            count=1,
            is_confirmed=False
        )
        # Add it to the database
        self.wallet.database.add(database_bundle)

        # Mock API response
        self.wallet.provider.get_all_bundles = lambda: succeed([bundle])
        self.wallet.provider.get_confirmations = lambda tx_hash: succeed(True)
        await self.wallet.update_bundles_database()
        # Get the bundle after the method
        bundle_after = self.wallet.database.query(DatabaseBundle) \
            .filter(DatabaseBundle.hash.__eq__(bundle.hash.__str__())) \
            .one()
        self.assertEqual(bundle_after.is_confirmed, True)
        self.assertEqual(bundle_after.hash, bundle.hash.__str__())
        self.wallet.cancel_all_pending_tasks()

    async def test_bundle_updates_no_bundle(self):
        """
        Tests that bundles' confirmation status isn not incorrectly updated
        """
        self.wallet.create_wallet()
        bundle = Bundle([self.tx1])
        # Make sure the bundle is not confirmed
        bundle.is_confirmed = False
        # Create DatabaseBundle based on tx1
        database_bundle = DatabaseBundle(
            hash=bundle.hash.__str__(),
            tail_transaction_hash=self.tx1.hash.__str__(),
            count=1,
            is_confirmed=False
        )
        # Add it to the database
        self.wallet.database.add(database_bundle)

        # Mock API response
        self.wallet.provider.get_all_bundles = lambda: succeed([bundle])
        self.wallet.provider.get_confirmations = lambda bundle_tail_hash: succeed(False)
        await self.wallet.update_bundles_database()
        # Get the bundle after the method
        bundle_after = self.wallet.database.query(DatabaseBundle) \
            .filter(DatabaseBundle.hash.__eq__(bundle.hash.__str__())) \
            .one()
        self.assertEqual(bundle_after.is_confirmed, bundle.is_confirmed)
        self.assertEqual(bundle_after.hash, bundle.hash.__str__())
        self.wallet.cancel_all_pending_tasks()

    async def test_bundle_no_tangle_bundles(self):
        """
        Tests updating the bundles when no transactions have occurred
        """
        self.wallet.create_wallet()

        async def bundles_db_mock():
            return []

        # Mock API response
        self.wallet.provider.get_all_bundles = bundles_db_mock
        await self.wallet.update_bundles_database()
        bundles_after = self.wallet.database.query(DatabaseBundle). \
            all()
        self.assertEqual(len(bundles_after), 0)
        self.wallet.cancel_all_pending_tasks()

    async def test_bundle_add_bundle_to_database(self):
        """
        Tests that new bundles are correctly inserted in the database
        """
        self.wallet.create_wallet()
        bundle = Bundle([self.tx1])
        # Create DatabaseBundle based on tx1
        expected = DatabaseBundle(
            hash=bundle.hash.__str__(),
            tail_transaction_hash='9TVXQWXUXFNDVXJI9JG9VPVQLWYLMNQEFHMRIDXXXMZNOHYHVNAUXFVQVSU9FORFJJWYXZVRZKEIETTYN',
            count=len(bundle.transactions),
            is_confirmed=False
        )

        # Mock API response
        self.wallet.provider.get_all_bundles = lambda: succeed([bundle])
        await self.wallet.update_bundles_database()
        # Get the bundle after the method
        bundles_after = self.wallet.database.query(DatabaseBundle) \
            .all()
        # Check that exactly one bundle has been added as a result
        self.assertEqual(1, len(bundles_after))
        # Get the only bundle
        bundle_after = bundles_after[0]
        # Check equivalence with the original
        self.assertEqual(expected.hash, bundle_after.hash)
        self.assertEqual(expected.tail_transaction_hash,
                         bundle_after.tail_transaction_hash)
        self.assertEqual(expected.count, bundle_after.count)
        self.assertEqual(expected.is_confirmed, bundle_after.is_confirmed)
        self.wallet.cancel_all_pending_tasks()


class TestIotaTestnetWallet(TestIotaWallet):

    def setUp(self):
        super(TestIotaWallet, self).setUp()
        self.wallet = self.new_wallet()
        self.identifier = 'TIOTA'
        self.name = 'testnet iota'
        self.testnet = True

    def new_wallet(self):
        return IotaTestnetWallet(self.session_base_dir)
