import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from main import App, SnakeGame, GRID, UP, RIGHT, DOWN, LEFT, SIZE, speed_for
from storage import load_profile, save_profile, empty_profile, record_round, data_file


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.game = SnakeGame()
        self.game.state = "playing"

    def test_apples_only_use_free_cells(self):
        self.game.snake = [(x, y) for y in range(GRID) for x in range(GRID) if (x, y) != (5, 5)]
        self.assertEqual(self.game.spawn_apple(), (5, 5))
        self.game.snake.append((5, 5))
        self.assertIsNone(self.game.spawn_apple())

    def test_eating_grows_at_destination_without_placeholder(self):
        self.game.apple = (14, 15)
        self.game.step()
        self.assertEqual(self.game.snake, [(14, 15), (15, 15), (16, 15), (17, 15)])
        self.assertEqual(self.game.score, 1)
        self.assertNotIn(self.game.apple, self.game.snake)

    def test_fast_turns_cannot_reverse_before_a_step(self):
        self.game.turn(UP)
        self.game.turn(RIGHT)
        self.game.step()
        self.assertEqual(self.game.direction, UP)
        self.assertEqual(self.game.snake[0], (15, 14))
        self.game.turn(RIGHT)
        self.game.step()
        self.assertEqual(self.game.snake[0], (16, 14))

    def test_reverse_is_ignored_without_blocking_a_valid_turn(self):
        self.game.turn(RIGHT)
        self.game.turn(UP)
        self.game.step()
        self.assertEqual(self.game.direction, UP)

    def test_same_direction_does_not_block_a_turn(self):
        self.game.turn(LEFT)
        self.game.turn(DOWN)
        self.game.step()
        self.assertEqual(self.game.direction, DOWN)

    def test_collision_with_all_four_walls_is_immediate(self):
        for head, direction in [((0, 10), LEFT), ((GRID - 1, 10), RIGHT), ((10, 0), UP), ((10, GRID - 1), DOWN)]:
            with self.subTest(direction=direction):
                self.game.reset()
                self.game.state = "playing"
                self.game.snake = [head]
                self.game.direction = self.game.next_direction = direction
                self.game.step()
                self.assertEqual(self.game.state, "over")
                self.assertEqual(self.game.snake[0], head)

    def test_body_collision_stops_without_changing_score(self):
        self.game.snake = [(1, 1), (1, 2), (2, 2), (2, 1), (3, 1)]
        self.game.direction = self.game.next_direction = RIGHT
        self.game.apple = (5, 5)
        self.game.step()
        self.assertEqual(self.game.state, "over")
        self.assertEqual(self.game.score, 0)

    def test_vacated_tail_cell_is_a_legal_move(self):
        self.game.snake = [(1, 1), (1, 2), (2, 2), (2, 1)]
        self.game.direction = self.game.next_direction = RIGHT
        self.game.apple = (5, 5)
        self.game.step()
        self.assertEqual(self.game.state, "playing")
        self.assertEqual(self.game.snake, [(2, 1), (1, 1), (1, 2), (2, 2)])

    def test_full_board_is_a_win_without_random_selection_error(self):
        self.game.snake = [(0, 0)] + [(x, y) for y in range(GRID) for x in range(GRID) if (x, y) not in [(0, 0), (1, 0)]]
        self.game.apple = (1, 0)
        self.game.direction = self.game.next_direction = RIGHT
        self.game.step()
        self.assertEqual(self.game.state, "won")
        self.assertEqual(len(self.game.snake), GRID * GRID)
        self.assertIsNone(self.game.apple)

    def test_stopped_game_does_not_move_or_accept_turns(self):
        self.game.state = "over"
        original = self.game.snake.copy()
        self.game.turn(UP)
        self.game.step()
        self.assertEqual(self.game.snake, original)
        self.assertEqual(self.game.direction, LEFT)

    def test_speed_increases_every_five_apples_and_has_a_limit(self):
        for mode, initial, maximum in [("easy", 6, 12), ("normal", 9, 16), ("hard", 12, 20)]:
            self.assertEqual(speed_for(mode, 0), initial)
            self.assertEqual(speed_for(mode, 4), initial)
            self.assertEqual(speed_for(mode, 5), initial + 1)
            self.assertEqual(speed_for(mode, 10), initial + 2)
            self.assertEqual(speed_for(mode, 897), maximum)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "data" / "profile.json"

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_and_corrupt_profiles_have_safe_defaults(self):
        self.assertEqual(load_profile(self.path), empty_profile())
        self.path.parent.mkdir()
        for value in ['null', '[]', 'broken', '{"settings": [], "scores": null}', '{"settings":{"difficulty": "unknown", "fullscreen": "yes"}}']:
            self.path.write_text(value, encoding="utf-8")
            self.assertEqual(load_profile(self.path), empty_profile())

    def test_records_are_separate_and_survive_reload(self):
        profile = empty_profile()
        record_round(profile, "easy", 10, 30, "over")
        record_round(profile, "hard", 5, 12, "interrupted")
        save_profile(self.path, profile)
        loaded = load_profile(self.path)
        self.assertEqual(loaded["scores"]["easy"]["record"], 10)
        self.assertEqual(loaded["scores"]["hard"]["record"], 5)
        self.assertEqual(loaded["scores"]["normal"]["record"], 0)
        self.assertFalse(self.path.with_name("profile.json.tmp").exists())

    def test_last_twenty_do_not_erase_top_five(self):
        profile = empty_profile()
        for score in [100, *range(25)]:
            record_round(profile, "normal", score, 15, "over")
        save_profile(self.path, profile)
        scores = load_profile(self.path)["scores"]["normal"]
        self.assertEqual(len(scores["history"]), 20)
        self.assertEqual([row["score"] for row in scores["best"]], [100, 24, 23, 22, 21])
        self.assertEqual(scores["record"], 100)

    def test_equal_score_is_not_a_new_record(self):
        profile = empty_profile()
        self.assertTrue(record_round(profile, "normal", 5, 15, "over"))
        self.assertFalse(record_round(profile, "normal", 5, 15, "over"))

    def test_invalid_rows_are_discarded(self):
        profile = empty_profile()
        record_round(profile, "normal", 5, 15, "over")
        row = profile["scores"]["normal"]["history"][0]
        invalid = [{**row, "score": True}, {**row, "score": 900}, {**row, "duration": float('nan')},
                   {**row, "date": "bad"}, {**row, "result": "unknown"}]
        profile["scores"]["normal"]["history"] = [*invalid, row]
        # Leitura de dados inválidos externos, não gravação pela aplicação.
        import json
        self.path.parent.mkdir()
        self.path.write_text(json.dumps(profile), encoding="utf-8")
        self.assertEqual(load_profile(self.path)["scores"]["normal"]["history"], [row])

    def test_storage_is_outside_the_installation(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": self.temporary.name}):
            self.assertEqual(data_file(), Path(self.temporary.name) / "AdrianoGames" / "SnakeGame" / "profile.json")


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "profile.json"
        self.app = App(self.path)

    def tearDown(self):
        pygame.quit()
        self.temporary.cleanup()

    def test_start_and_restart_reset_the_round(self):
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.game.state, "countdown")
        self.app.game.score = 10
        self.app.game.turn(UP)
        self.app.game.state = "over"
        self.app.elapsed = 0.04
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        self.assertEqual(self.app.game.score, 0)
        self.assertEqual(self.app.game.snake, [(15, 15), (16, 15), (17, 15)])
        self.assertEqual(self.app.elapsed, 0)
        self.assertEqual(self.app.game.direction, LEFT)

    def test_game_waits_for_start_and_over_has_no_updates(self):
        initial = self.app.game.snake.copy()
        self.app.update(1)
        self.assertEqual(self.app.game.snake, initial)
        self.app.game.state = "over"
        with patch.object(self.app.game, "step") as step:
            self.app.update(1)
            step.assert_not_called()

    def test_movement_has_a_fixed_interval(self):
        self.app.start()
        for _ in range(30):
            self.app.update(0.1)
        interval = 1 / speed_for("normal", 0)
        self.app.update(interval / 2)
        self.assertEqual(self.app.game.snake[0], (15, 15))
        self.app.update(interval / 2)
        self.assertEqual(self.app.game.snake[0], (14, 15))

    def test_movement_is_consistent_at_different_frame_rates(self):
        results = []
        for fps in (60, 120):
            self.app.start()
            self.app.game.state = "playing"
            self.app.round_active = True
            self.app.game.apple = (5, 5)
            for _ in range(int(fps * 0.4)):
                self.app.update(1 / fps)
            results.append((self.app.game.snake[0], self.app.duration))
        self.assertEqual(results[0][0], results[1][0])
        self.assertAlmostEqual(results[0][1], results[1][1])

    def test_all_screens_render(self):
        for size in [(600, 714), (320, 480), (900, 540)]:
            self.app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1]))
            for state in ("ready", "playing", "over", "won", "paused", "countdown", "settings", "ranking", "history"):
                self.app.game.state = state
                self.app.draw()

    def test_quit_and_escape_work_from_every_screen(self):
        for state in ("ready", "playing", "over", "won"):
            for event in (pygame.event.Event(pygame.QUIT),):
                self.app.running = True
                self.app.game.state = state
                self.app.handle_event(event)
                self.assertFalse(self.app.running)

    def test_escape_pauses_returns_to_menu_and_exits(self):
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        self.app.game.state = "playing"
        self.app.handle_event(escape)
        self.assertEqual(self.app.game.state, "paused")
        self.app.handle_event(escape)
        self.assertEqual(self.app.game.state, "countdown")
        self.app.game.state = "over"
        self.app.handle_event(escape)
        self.assertEqual(self.app.game.state, "ready")
        self.app.handle_event(escape)
        self.assertFalse(self.app.running)

    def test_countdown_and_pause_freeze_time_and_movement(self):
        self.app.start()
        initial = self.app.game.snake.copy()
        self.app.update(0.1)
        self.assertEqual(self.app.duration, 0)
        self.assertEqual(self.app.game.snake, initial)
        for _ in range(29):
            self.app.update(0.1)
        self.assertEqual(self.app.game.state, "playing")
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
        self.app.elapsed = 0.04
        self.app.update(0.1)
        self.assertEqual(self.app.elapsed, 0.04)
        self.assertEqual(self.app.game.snake, initial)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
        self.assertEqual(self.app.countdown, 3)

    def test_focus_loss_pauses_without_automatic_resume(self):
        for state in ("playing", "countdown"):
            self.app.game.state = state
            self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
            self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            self.assertEqual(self.app.game.state, "paused")

    def test_history_is_saved_once_and_never_for_initial_countdown(self):
        self.app.start()
        self.app.activate("menu")
        self.assertEqual(self.app.profile["scores"]["normal"]["history"], [])
        self.app.start()
        for _ in range(30):
            self.app.update(0.1)
        self.app.game.score = 5
        self.app.duration = 12
        self.app.game.state = "over"
        self.app.finish("over")
        self.app.finish("over")
        self.assertEqual(len(load_profile(self.path)["scores"]["normal"]["history"]), 1)
        self.assertTrue(self.app.new_record)

    def test_quitting_resume_countdown_saves_interrupted_round(self):
        self.app.round_active = True
        self.app.game.score = 8
        self.app.resume()
        self.app.activate("exit")
        row = load_profile(self.path)["scores"]["normal"]["history"][0]
        self.assertEqual(row["result"], "interrupted")
        self.assertEqual(row["score"], 8)

    def test_difficulty_is_saved_but_score_filter_does_not_change_it(self):
        self.app.activate("difficulty")
        self.assertEqual(load_profile(self.path)["settings"]["difficulty"], "hard")
        self.app.start()
        self.assertEqual(self.app.game.difficulty, "hard")
        self.app.activate("menu")
        self.app.activate("ranking")
        self.app.activate("view_mode")
        self.assertEqual(self.app.view_mode, "easy")
        self.assertEqual(self.app.profile["settings"]["difficulty"], "hard")

    def test_mouse_coordinates_use_letterboxing(self):
        self.app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=1000, h=600))
        area = self.app.scene_geometry()
        self.assertIsNone(self.app.logical_point((0, 0)))
        point = (round(area.x + 100 * area.width / SIZE[0]), round(area.y + 355 * area.height / SIZE[1]))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.assertEqual(self.app.game.state, "countdown")

    def test_save_failure_does_not_break_menu(self):
        with patch("main.save_profile", side_effect=OSError("disk unavailable")):
            self.app.activate("difficulty")
        self.assertTrue(self.app.notice)
        self.app.activate("menu")
        self.assertEqual(self.app.game.state, "ready")

    def test_fullscreen_toggle_saves_preference_and_preserves_window(self):
        window_size = self.app.screen.get_size()
        with patch("pygame.display.set_mode", return_value=self.app.screen) as display:
            self.app.activate("fullscreen")
            self.assertTrue(load_profile(self.path)["settings"]["fullscreen"])
            display.assert_called_with((0, 0), pygame.FULLSCREEN)
            self.app.activate("fullscreen")
            display.assert_called_with(window_size, pygame.RESIZABLE)

    def test_fullscreen_failure_reports_error_without_changing_preference(self):
        with patch("pygame.display.set_mode", side_effect=pygame.error("unavailable")):
            self.app.activate("fullscreen")
        self.assertFalse(self.app.fullscreen)
        self.assertTrue(self.app.notice)

    def test_history_pagination_and_empty_views_render(self):
        for score in range(7):
            record_round(self.app.profile, "normal", score, 15, "over")
        self.app.activate("history")
        self.app.activate("next")
        self.assertEqual(self.app.history_page, 1)
        self.app.draw()
        self.app.activate("view_mode")
        self.assertEqual(self.app.history_page, 0)
        self.app.draw()

    def test_old_valid_dates_do_not_crash_score_screens_on_windows(self):
        record_round(self.app.profile, "normal", 5, 15, "over")
        row = self.app.profile["scores"]["normal"]["history"][0]
        for date in ("0001-01-01", "1899-12-31T23:59:59", "9999-12-31T23:59:59"):
            row["date"] = date
            for state in ("ranking", "history"):
                self.app.activate(state)
                self.app.draw()

    def test_mouse_hover_and_keyboard_use_the_same_selected_button(self):
        area = self.app.scene_geometry()
        point = (round(area.x + 100 * area.width / SIZE[0]), round(area.y + 480 * area.height / SIZE[1]))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=point))
        self.assertEqual(self.app.menu_index, 2)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.game.state, "settings")

    def test_clicking_settings_keeps_keyboard_selection_in_sync(self):
        self.app.activate("settings")
        area = self.app.scene_geometry()
        point = (round(area.x + 100 * area.width / SIZE[0]), round(area.y + 465 * area.height / SIZE[1]))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=point))
        self.assertEqual(self.app.menu_index, 2)
        point = (round(area.x + 100 * area.width / SIZE[0]), round(area.y + 325 * area.height / SIZE[1]))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.assertEqual(self.app.menu_index, 0)
        self.assertEqual(self.app.profile["settings"]["difficulty"], "hard")

    def test_minimizing_and_resizing_pause_the_round(self):
        for state in ("playing", "countdown"):
            for event in (pygame.event.Event(pygame.WINDOWMINIMIZED), pygame.event.Event(pygame.VIDEORESIZE, w=640, h=480)):
                self.app.game.state = state
                initial = self.app.game.snake.copy(), self.app.duration
                self.app.handle_event(event)
                self.app.update(0.1)
                self.assertEqual(self.app.game.state, "paused")
                self.assertEqual(initial, (self.app.game.snake, self.app.duration))

    def test_exit_retries_a_failed_save_without_duplicating_the_round(self):
        self.app.round_active = True
        self.app.game.score = 7
        with patch("main.save_profile", side_effect=OSError("temporarily unavailable")):
            self.app.finish("over")
        self.assertTrue(self.app.pending_save)
        self.app.activate("exit")
        self.assertFalse(self.app.pending_save)
        rows = load_profile(self.path)["scores"]["normal"]["history"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["score"], 7)

    def test_events_after_quit_cannot_start_a_new_round(self):
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.game.state, "ready")
        self.assertFalse(self.app.running)

    def test_one_loop_caps_frames_even_after_game_over(self):
        self.app.game.state = "over"
        self.app.clock = unittest.mock.Mock()
        self.app.clock.tick.return_value = 16
        with patch("pygame.event.get", side_effect=[[], [pygame.event.Event(pygame.QUIT)]]), patch.object(self.app, "draw") as draw:
            self.app.run()
        self.assertEqual(self.app.clock.tick.call_args_list, [unittest.mock.call(60), unittest.mock.call(60)])
        draw.assert_called_once()


if __name__ == "__main__":
    unittest.main()
