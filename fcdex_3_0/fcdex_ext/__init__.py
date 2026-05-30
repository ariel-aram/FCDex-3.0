from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    from fcdex_3_0.fcdex_ext.achievement_cog import AchievementCog
    from fcdex_3_0.fcdex_ext.battle_cog import BattleCog
    from fcdex_3_0.fcdex_ext.fcdex_cog import FcdexCog
    from fcdex_3_0.fcdex_ext.merge_cog import MergeCog
    from fcdex_3_0.fcdex_ext.merge_special import bootstrap_merge_special
    from fcdex_3_0.fcdex_ext.tournament_cog import TournamentCog

    await bootstrap_merge_special(bot)
    await bot.add_cog(FcdexCog(bot))
    await bot.add_cog(BattleCog(bot))
    await bot.add_cog(MergeCog(bot))
    await bot.add_cog(AchievementCog(bot))
    await bot.add_cog(TournamentCog(bot))
