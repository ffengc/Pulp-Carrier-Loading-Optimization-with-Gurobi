# ------------------------------- README ------------------------------- #
#                                                                        #
#                                                                        #
#                      请使用当前目录下的运行脚本运行代码                   #
#                         bash ./start_optimal.sh                        #
#                           如果直接运行main.py文件                        #
#                      Gurobi的日志并不会输出到run.log中                   #
#                                                                        #
#                                                                        #
# ------------------------------- README ------------------------------- #

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from gurobipy import Model

# ------------------------------- 数据分离部分begin ------------------------------- #

# 四个重要变量
compartments_num = 6  # 一共有6个仓舱
floors_in_each_compartment_num = 10  # 每个舱有10层
loading_sites_num = 3  # 装载地的数量
destination_num = 4  # 目的地的数量

project_root_path = "/Users/demac/Desktop/src/op-main/"


# 载入load_storage到storage_set_dict中
def load_storage(arr) -> dict:
    # 定义各舱室各层的最大容量(i,j)表示第i舱第j层的最大容量
    C = {}
    for ii in range(0, len(arr)):
        for jj in range(0, len(arr[ii])):
            # (ii,jj) 表示第ii行第jj列 -> 第ii+1层，在第jj+1舱，(jj+1,ii+1)表示第jj舱的第ii列
            C[(jj + 1, ii + 1)] = arr[ii][jj]
    return C


# 初始化storage字典
storage_set_dict = None


def init_storage():
    # 读取存储容量信息的csv
    df = pd.read_csv(project_root_path + "./storage.conf")
    arr = df.to_numpy().tolist()
    global storage_set_dict
    storage_set_dict = load_storage(
        arr
    )  # storage_set_dict是字典 (i,j)=storage, 第i舱第j层的最大容量为storage


# 通过src找到能提供的装载数量
def src2provide(src) -> int:
    assert src >= 1 and src <= 3
    provide = [9320, 6480, 13200]  # provide[i]表示i+1装载地能提供的数量
    return provide[src - 1]


# 通过(src, dest)找到对应的需求
def pair2demand(src, dest) -> int:
    demand_dict = {
        (1, 1): 0,
        (2, 1): 2835,
        (3, 1): 1575,
        (1, 2): 360,
        (2, 2): 3645,
        (3, 2): 4725,
        (1, 3): 6355,
        (2, 3): 0,
        (3, 3): 2490,
        (1, 4): 2605,
        (2, 4): 0,
        (3, 4): 4410,
    }
    return demand_dict[(src, dest)]


# 通过(carbin, floor)找到对应的容量
def pair2storage(cabin, floor) -> int:
    return storage_set_dict[(cabin, floor)]


# ------------------------------- 数据分离部分end ------------------------------- #


# ------------------------------- 模型运行部分 ------------------------------- #


# 输出模型求解的结果
def output_optimal_solution(model, model_write_path, iterator):
    print("The optimal solution is founded.")
    # 保存模型的求解过程
    model.write(model_write_path)
    # 打印每个决策变量的值
    for iter in iterator:
        if iterator[iter][0].X > 0:
            print(
                f"goods in ({iter[0]},{iter[1]}):<{iter[2]}->{iter[3]}>:{iterator[iter][0].X}"
            )
    # 打印目标函数的值
    print(f"Optimal objective value: {model.ObjVal}")
    for j in range(floors_in_each_compartment_num, 0, -1):
        for i in range(1, compartments_num + 1):
            for s in range(1, loading_sites_num + 1):
                for d in range(1, destination_num + 1):
                    if iterator[i, j, s, d][0].X != 0:
                        print(f"({s}, {d}):{iterator[i,j,s,d][0].X}", end="\t")
        print()


# 定义辅助变量大M
M = 1e5
# 初始化货物存放的约束
init_storage()
# 定义模型
model = Model("CargoShipping")

# 定义决策变量
iterator = {}
# iterator是一个kv结构，k为一个4个元素的tuple，表示一种可能组合，v是一个2个元素的tuple，第一个元素表示
# 装载的量，第二个元素表示是否有装载，如果第一个元素非0，则第二个元素为1，否则为0
for cur_compartments_num in range(1, compartments_num + 1):
    for cur_floors_in_each_compartment_num in range(
        1, floors_in_each_compartment_num + 1
    ):
        for cur_loading_sites_num in range(1, loading_sites_num + 1):
            for cur_destination_num in range(1, destination_num + 1):
                # 四层循环进行遍历
                cur_tuple = (
                    cur_compartments_num,
                    cur_floors_in_each_compartment_num,
                    cur_loading_sites_num,
                    cur_destination_num,
                )
                element1 = model.addVar(vtype=GRB.INTEGER, name=f"goods_{cur_tuple}")
                element2 = model.addVar(vtype=GRB.BINARY, name=f"is_goods_{cur_tuple}")
                iterator[cur_tuple] = (element1, element2)  # 初始化元组
                iterator[cur_tuple][1].Start = 0
                # 添加约束
                model.addConstr(iterator[cur_tuple][0] >= 0)
                model.addConstr(iterator[cur_tuple][1] >= iterator[cur_tuple][0] / M)

# ------------------------------- 定义约束条件 ------------------------------- #

# 约束1
# 舱室容量限制，第i舱室第j层的货量不能超过设定的值
for i in range(1, compartments_num + 1):
    for j in range(1, floors_in_each_compartment_num + 1):
        cur_room_sum = gp.quicksum(
            iterator[i, j, s, d][0]
            for s in range(1, loading_sites_num + 1)
            for d in range(1, destination_num + 1)
        )
        # 添加约束
        model.addConstr(cur_room_sum <= pair2storage(i, j))

# 约束2
# 装载地供应限制，所有从装载地loading_sites_num装载的纸浆包数量不能超过设定值
for s in range(1, loading_sites_num + 1):
    cur_s_load_sum = gp.quicksum(
        iterator[i, j, s, d][0]
        for i in range(1, compartments_num + 1)
        for j in range(1, floors_in_each_compartment_num + 1)
        for d in range(1, destination_num + 1)
    )
    # 添加约束
    model.addConstr(cur_s_load_sum <= src2provide(s))

# 约束3
# 送达地需求限制，所有送达地d的需求必须满足到货量要等于需求
for s in range(1, loading_sites_num + 1):
    for d in range(1, destination_num + 1):
        cur_get_num = gp.quicksum(
            iterator[i, j, s, d][0]
            for i in range(1, compartments_num + 1)
            for j in range(1, floors_in_each_compartment_num + 1)
        )
        # 添加约束
        model.addConstr(cur_get_num == pair2demand(s, d))

# 约束4
# 装卸限制，由于船舶是从装载地 1 出发，顺序经过装载地 1、2、3、送达地 A、B、C、D
for i in range(1, compartments_num + 1):
    for j in range(1, floors_in_each_compartment_num + 1):
        for s in range(1, loading_sites_num + 1):
            # 控制装载顺序
            the_goods_from_s = model.addVar(vtype=GRB.BINARY)
            model.addConstrs(
                the_goods_from_s >= iterator[(i, j, s, d_)][1] / M
                for d_ in range(1, destination_num + 1)
            )
            the_goods_load_behind_s = model.addVar(vtype=GRB.BINARY)
            model.addConstrs(
                the_goods_load_behind_s >= iterator[(i, j_, s_, d_)][1] / M
                for j_ in range(1, j)
                for s_ in range(s + 1, loading_sites_num + 1)
                for d_ in range(1, destination_num + 1)
            )
            model.addGenConstrIndicator(
                the_goods_from_s, 1, the_goods_load_behind_s == 0
            )
        for d in range(1, destination_num + 1):
            # 控制卸货顺序
            the_goods_to_d = model.addVar(vtype=GRB.BINARY)
            model.addConstrs(
                the_goods_to_d >= iterator[(i, j, s_, d)][1] / M
                for s_ in range(1, loading_sites_num + 1)
            )
            the_goods_behind_to_d = model.addVar(vtype=GRB.BINARY)
            model.addConstrs(
                the_goods_behind_to_d >= iterator[(i, j_, s_, d_)][1] / M
                for j_ in range(1, j)
                for s_ in range(1, loading_sites_num + 1)
                for d_ in range(1, d)
            )
            model.addGenConstrIndicator(the_goods_to_d, 1, the_goods_behind_to_d == 0)


# 约束5
# 在每个装载或卸载地时，不能同时打开 2、3 舱和 4、5 舱
for s in range(1, loading_sites_num + 1):
    goods_load_from_s_c2 = model.addVar(vtype=GRB.BINARY)
    goods_load_from_s_c3 = model.addVar(vtype=GRB.BINARY)
    goods_load_from_s_c4 = model.addVar(vtype=GRB.BINARY)
    goods_load_from_s_c5 = model.addVar(vtype=GRB.BINARY)
    model.addConstrs(
        goods_load_from_s_c2 >= iterator[2, j, s, d_][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for d_ in range(1, destination_num + 1)
    )
    model.addConstrs(
        goods_load_from_s_c3 >= iterator[3, j, s, d_][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for d_ in range(1, destination_num + 1)
    )
    model.addConstrs(
        goods_load_from_s_c4 >= iterator[4, j, s, d_][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for d_ in range(1, destination_num + 1)
    )
    model.addConstrs(
        goods_load_from_s_c5 >= iterator[5, j, s, d_][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for d_ in range(1, destination_num + 1)
    )
    # 添加约束
    model.addConstr(goods_load_from_s_c2 + goods_load_from_s_c3 <= 1)
    model.addConstr(goods_load_from_s_c4 + goods_load_from_s_c5 <= 1)

for d in range(1, destination_num + 1):
    goods_deload_to_d_c2 = model.addVar(vtype=GRB.BINARY)
    goods_deload_to_d_c3 = model.addVar(vtype=GRB.BINARY)
    goods_deload_to_d_c4 = model.addVar(vtype=GRB.BINARY)
    goods_deload_to_d_c5 = model.addVar(vtype=GRB.BINARY)
    model.addConstrs(
        goods_deload_to_d_c2 >= iterator[2, j, s_, d][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for s_ in range(1, loading_sites_num + 1)
    )
    model.addConstrs(
        goods_deload_to_d_c3 >= iterator[3, j, s_, d][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for s_ in range(1, loading_sites_num + 1)
    )
    model.addConstrs(
        goods_deload_to_d_c4 >= iterator[4, j, s_, d][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for s_ in range(1, loading_sites_num + 1)
    )
    model.addConstrs(
        goods_deload_to_d_c5 >= iterator[5, j, s_, d][0] / M
        for j in range(1, floors_in_each_compartment_num + 1)
        for s_ in range(1, loading_sites_num + 1)
    )
    # 添加约束
    model.addConstr(goods_deload_to_d_c2 + goods_deload_to_d_c3 <= 1)
    model.addConstr(goods_deload_to_d_c4 + goods_deload_to_d_c5 <= 1)


# 更新模型以集成变量和约束
model.update()


# ------------------------------- 定义优化目标 ------------------------------- #

# 目标函数
# 不同装载地-送达地的纸浆包混装在同层的次数尽可能少
model.setObjective(
    gp.quicksum(
        iterator[i, j, s, d][1]
        for i in range(1, compartments_num + 1)
        for j in range(1, floors_in_each_compartment_num + 1)
        for s in range(1, loading_sites_num + 1)
        for d in range(1, destination_num + 1)
    ),
    GRB.MINIMIZE,
)

# ------------------------------- 求解模型 ------------------------------- #

model.Params.MIPFocus = 3

# 开始求解结果
model.optimize()

# ------------------------------- 记录结果 ------------------------------- #

if model.status == GRB.OPTIMAL:
    model_write_path = project_root_path + "./model.lp"
    output_optimal_solution(model, model_write_path, iterator)
elif model.status == GRB.INFEASIBLE:
    print("Cannot found solution")
elif model.status == GRB.INF_OR_UNBD:
    print("The model has no solution or is unbounded")
else:
    print("The optimization process was not successfully completed")
