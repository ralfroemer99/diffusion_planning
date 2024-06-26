# import sys
# sys.path.append('../diffuser/')
# sys.path.append('../envs/')
# from .. import diffuser
import diffuser.utils as utils
# from . import envs
from envs.quad_2d import Quad2DEnv
from envs.pointmass import PointMassEnv


#-----------------------------------------------------------------------------#
#----------------------------------- setup -----------------------------------#
#-----------------------------------------------------------------------------#
train = 1
train_values = 1

exp = 'quad2d'  # 'pointmass' or 'quad2d

class Parser(utils.Parser):
    dataset: str = exp
    config: str = 'config.' + exp
    
#---------------------------------- dataset ----------------------------------#

if exp == 'pointmass':
    env = PointMassEnv(target=None, max_steps=20, epsilon=0.2, reset_target_reached=False, bonus_reward=False, 
                reset_out_of_bounds=True, theta_as_sine_cosine=True, num_episodes=1000)
else:
    env = Quad2DEnv(min_rel_thrust=0.75, max_rel_thrust=1.25, 
                max_rel_thrust_difference=0.01, target=None, max_steps=20,
                epsilon=0.5, reset_target_reached=False, bonus_reward=False, 
                reset_out_of_bounds=True, theta_as_sine_cosine=True, num_episodes=1000)

#-----------------------------------------------------------------------------#
#------------------------------ Diffusion model ------------------------------#
#-----------------------------------------------------------------------------#
if train:
    args = Parser().parse_args('diffusion')
    dataset_config = utils.Config(
        args.loader,
        savepath=(args.savepath, 'dataset_config.pkl'),
        env=env,
        horizon=args.horizon,
        normalizer=args.normalizer,
        preprocess_fns=args.preprocess_fns,
        use_padding=args.use_padding,
        use_actions=args.use_actions,
        max_path_length=args.max_path_length,
    )

    dataset = dataset_config()

    observation_dim = dataset.observation_dim
    action_dim = dataset.action_dim
    goal_dim = dataset.goal_dim

    #------------------------------ model & trainer ------------------------------#

    model_config = utils.Config(
        args.model,
        savepath=(args.savepath, 'model_config.pkl'),
        horizon=args.horizon,
        transition_dim=observation_dim + action_dim,
        cond_dim=observation_dim,
        dim_mults=args.dim_mults,
        attention=args.attention,
        device=args.device,
    )

    diffusion_config = utils.Config(
        args.diffusion,
        savepath=(args.savepath, 'diffusion_config.pkl'),
        horizon=args.horizon,
        observation_dim=observation_dim,
        action_dim=action_dim,
        goal_dim=goal_dim,
        n_timesteps=args.n_diffusion_steps,
        loss_type=args.loss_type,
        clip_denoised=args.clip_denoised,
        predict_epsilon=args.predict_epsilon,
        ## loss weighting
        action_weight=args.action_weight,
        loss_weights=args.loss_weights,
        loss_discount=args.loss_discount,
        device=args.device,
    )

    trainer_config = utils.Config(
        utils.Trainer,
        savepath=(args.savepath, 'trainer_config.pkl'),
        train_batch_size=args.batch_size,
        train_lr=args.learning_rate,
        gradient_accumulate_every=args.gradient_accumulate_every,
        ema_decay=args.ema_decay,
        train_test_split=args.train_test_split,
        sample_freq=args.sample_freq,
        save_freq=args.save_freq,
        label_freq=int(args.n_train_steps // args.n_saves),
        save_parallel=args.save_parallel,
        results_folder=args.savepath,
        bucket=args.bucket,
        n_reference=args.n_reference,
    )

    #-------------------------------- instantiate --------------------------------#

    model = model_config()

    diffusion = diffusion_config(model)

    trainer = trainer_config(diffusion, dataset)

    #------------------------ test forward & backward pass -----------------------#

    utils.report_parameters(model)

    print('Testing forward...', end=' ', flush=True)
    batch = utils.batchify(dataset[0])
    loss, _ = diffusion.loss(*batch)    
    loss.backward()
    print('✓')


    #--------------------------------- main loop ---------------------------------#

    n_epochs = int(args.n_train_steps // args.n_steps_per_epoch)

    for i in range(n_epochs):
        if i % 10 == 0:
            print(f'Epoch {i} / {n_epochs} | {args.savepath}')
        trainer.train(n_train_steps=args.n_steps_per_epoch)
        # if args.train_test_split < 1:
        #     trainer.test()


#-----------------------------------------------------------------------------#
#-------------------------------- Value model --------------------------------#
#-----------------------------------------------------------------------------#
        
if train_values:
    args = Parser().parse_args('values')

    dataset_config = utils.Config(
        args.loader,
        savepath=(args.savepath, 'dataset_config.pkl'),
        env=env,
        horizon=args.horizon,
        normalizer=args.normalizer,
        preprocess_fns=args.preprocess_fns,
        use_padding=args.use_padding,
        use_actions=args.use_actions,
        max_path_length=args.max_path_length,
        ## value-specific kwargs
        discount=args.discount,
        termination_penalty=args.termination_penalty,
        normed=args.normed,
    )

    dataset = dataset_config()

    observation_dim = dataset.observation_dim
    action_dim = dataset.action_dim
    goal_dim = dataset.goal_dim

    #------------------------------ model & trainer ------------------------------#

    model_config = utils.Config(
        args.model,
        savepath=(args.savepath, 'model_config.pkl'),
        horizon=args.horizon,
        transition_dim=observation_dim + action_dim,
        cond_dim=observation_dim,
        dim_mults=args.dim_mults,
        device=args.device,
    )

    diffusion_config = utils.Config(
        args.diffusion,
        savepath=(args.savepath, 'diffusion_config.pkl'),
        horizon=args.horizon,
        observation_dim=observation_dim,
        action_dim=action_dim,
        goal_dim=goal_dim,
        n_timesteps=args.n_diffusion_steps,
        loss_type=args.loss_type,
        device=args.device,
    )

    trainer_config = utils.Config(
        utils.Trainer,
        savepath=(args.savepath, 'trainer_config.pkl'),
        train_batch_size=args.batch_size,
        train_lr=args.learning_rate,
        gradient_accumulate_every=args.gradient_accumulate_every,
        ema_decay=args.ema_decay,
        train_test_split=args.train_test_split,
        sample_freq=args.sample_freq,
        save_freq=args.save_freq,
        label_freq=int(args.n_train_steps // args.n_saves),
        save_parallel=args.save_parallel,
        results_folder=args.savepath,
        bucket=args.bucket,
        n_reference=args.n_reference,
    )

    #-------------------------------- instantiate --------------------------------#

    model = model_config()

    diffusion = diffusion_config(model)

    trainer = trainer_config(diffusion, dataset)

    #------------------------ test forward & backward pass -----------------------#

    utils.report_parameters(model)

    print('Testing forward...', end=' ', flush=True)
    batch = utils.batchify(dataset[0])
    loss, _ = diffusion.loss(*batch)
    loss.backward()
    print('✓')

    #--------------------------------- main loop ---------------------------------#

    n_epochs = int(args.n_train_steps // args.n_steps_per_epoch)

    for i in range(n_epochs):
        if i % 10 == 0:
            print(f'Epoch {i} / {n_epochs} | {args.savepath}')
        trainer.train(n_train_steps=args.n_steps_per_epoch)





#-----------------------------------------------------------------------------#
#------------------------------ Diffusion model ------------------------------#
#-----------------------------------------------------------------------------#
# if train:
#     args = Parser().parse_args('diffusion')
#     dataset_config = utils.Config(
#         args.loader,
#         savepath=(args.savepath, 'dataset_config.pkl'),
#         env=env,
#         horizon=args.horizon,
#         normalizer=args.normalizer,
#         preprocess_fns=args.preprocess_fns,
#         use_padding=args.use_padding,
#         use_actions=False,
#         max_path_length=args.max_path_length,
#     )

#     dataset = dataset_config()

#     observation_dim = dataset.observation_dim
#     action_dim = dataset.action_dim
#     goal_dim = dataset.goal_dim

#     #------------------------------ model & trainer ------------------------------#

#     model_config = utils.Config(
#         args.model,
#         savepath=(args.savepath, 'model_config.pkl'),
#         horizon=args.horizon,
#         transition_dim=observation_dim + action_dim,
#         cond_dim=observation_dim,
#         dim_mults=args.dim_mults,
#         attention=args.attention,
#         device=args.device,
#     )

#     diffusion_config = utils.Config(
#         args.diffusion,
#         savepath=(args.savepath, 'diffusion_config.pkl'),
#         horizon=args.horizon,
#         observation_dim=observation_dim,
#         action_dim=action_dim,
#         goal_dim=goal_dim,
#         n_timesteps=args.n_diffusion_steps,
#         loss_type=args.loss_type,
#         clip_denoised=args.clip_denoised,
#         predict_epsilon=args.predict_epsilon,
#         ## loss weighting
#         action_weight=args.action_weight,
#         loss_weights=args.loss_weights,
#         loss_discount=args.loss_discount,
#         device=args.device,
#     )

#     trainer_config = utils.Config(
#         utils.Trainer,
#         savepath=(args.savepath, 'trainer_config.pkl'),
#         train_batch_size=args.batch_size,
#         train_lr=args.learning_rate,
#         gradient_accumulate_every=args.gradient_accumulate_every,
#         ema_decay=args.ema_decay,
#         train_test_split=args.train_test_split,
#         sample_freq=args.sample_freq,
#         save_freq=args.save_freq,
#         label_freq=int(args.n_train_steps // args.n_saves),
#         save_parallel=args.save_parallel,
#         results_folder=args.savepath,
#         bucket=args.bucket,
#         n_reference=args.n_reference,
#     )

#     #-------------------------------- instantiate --------------------------------#

#     model = model_config()

#     diffusion = diffusion_config(model)

#     trainer = trainer_config(diffusion, dataset)

#     #------------------------ test forward & backward pass -----------------------#

#     utils.report_parameters(model)

#     print('Testing forward...', end=' ', flush=True)
#     batch = utils.batchify(dataset[0])
#     loss, _ = diffusion.loss(*batch)    
#     loss.backward()
#     print('✓')


#     #--------------------------------- main loop ---------------------------------#

#     n_epochs = int(args.n_train_steps // args.n_steps_per_epoch)

#     for i in range(n_epochs):
#         if i % 10 == 0:
#             print(f'Epoch {i} / {n_epochs} | {args.savepath}')
#         trainer.train(n_train_steps=args.n_steps_per_epoch)
#         # if args.train_test_split < 1:
#         #     trainer.test()


# #-----------------------------------------------------------------------------#
# #-------------------------------- Value model --------------------------------#
# #-----------------------------------------------------------------------------#
        
# if train_values:
#     args = Parser().parse_args('values')

#     dataset_config = utils.Config(
#         args.loader,
#         savepath=(args.savepath, 'dataset_config.pkl'),
#         env=env,
#         horizon=args.horizon,
#         normalizer=args.normalizer,
#         preprocess_fns=args.preprocess_fns,
#         use_padding=args.use_padding,
#         use_actions=False,
#         max_path_length=args.max_path_length,
#         ## value-specific kwargs
#         discount=args.discount,
#         termination_penalty=args.termination_penalty,
#         normed=args.normed,
#     )

#     dataset = dataset_config()

#     observation_dim = dataset.observation_dim
#     action_dim = dataset.action_dim
#     goal_dim = dataset.goal_dim

#     #------------------------------ model & trainer ------------------------------#

#     model_config = utils.Config(
#         args.model,
#         savepath=(args.savepath, 'model_config.pkl'),
#         horizon=args.horizon,
#         transition_dim=observation_dim + action_dim,
#         cond_dim=observation_dim,
#         dim_mults=args.dim_mults,
#         device=args.device,
#     )

#     diffusion_config = utils.Config(
#         args.diffusion,
#         savepath=(args.savepath, 'diffusion_config.pkl'),
#         horizon=args.horizon,
#         observation_dim=observation_dim,
#         action_dim=action_dim,
#         goal_dim=goal_dim,
#         n_timesteps=args.n_diffusion_steps,
#         loss_type=args.loss_type,
#         device=args.device,
#     )

#     trainer_config = utils.Config(
#         utils.Trainer,
#         savepath=(args.savepath, 'trainer_config.pkl'),
#         train_batch_size=args.batch_size,
#         train_lr=args.learning_rate,
#         gradient_accumulate_every=args.gradient_accumulate_every,
#         ema_decay=args.ema_decay,
#         train_test_split=args.train_test_split,
#         sample_freq=args.sample_freq,
#         save_freq=args.save_freq,
#         label_freq=int(args.n_train_steps // args.n_saves),
#         save_parallel=args.save_parallel,
#         results_folder=args.savepath,
#         bucket=args.bucket,
#         n_reference=args.n_reference,
#     )

#     #-------------------------------- instantiate --------------------------------#

#     model = model_config()

#     diffusion = diffusion_config(model)

#     trainer = trainer_config(diffusion, dataset)

#     #------------------------ test forward & backward pass -----------------------#

#     utils.report_parameters(model)

#     print('Testing forward...', end=' ', flush=True)
#     batch = utils.batchify(dataset[0])
#     loss, _ = diffusion.loss(*batch)
#     loss.backward()
#     print('✓')

#     #--------------------------------- main loop ---------------------------------#

#     n_epochs = int(args.n_train_steps // args.n_steps_per_epoch)

#     for i in range(n_epochs):
#         if i % 10 == 0:
#             print(f'Epoch {i} / {n_epochs} | {args.savepath}')
#         trainer.train(n_train_steps=args.n_steps_per_epoch)
