"""a142 Cycle Basis -- select permutation generators rather than move pieces directly."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BOARD,PIECE_A,PIECE_B,CYCLE,SELECTED,CURSOR,TARGET,RANK,EXCESS=9,8,12,14,10,13,11,4,6,7
BAD=15
LEVELS=[
 {"name":"Select Generator","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Change Target","seq":(3,1)},{"name":"Generate Permutation","seq":(1,2,3,4,2)},
 {"name":"Small Basis","seq":(1,3,2,1,4,3,2)},{"name":"Cycle Basis","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 selected,cursor,target,rank,excess,history,snapshot=s
 if a==1:selected^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:target=(target+1)%5;history=(history+(3,))[-8:]
 elif a==4:count=selected.bit_count();rank=min(5,count+int(selected&0b10101!=0));excess=max(0,count-(2+target%2));history=(history+(4,))[-8:]
 elif a==5:snapshot=(selected,cursor,target,rank,excess,history)
 return selected,cursor,target,rank,excess,history,snapshot
for q in LEVELS:
 s=(0b000101,0,0,2,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BOARD;pts=((15,15),(31,10),(47,15),(47,43),(31,50),(15,43))
  for i,(x,y) in enumerate(pts):
   f[y-5:y+6,x-5:x+6]=PIECE_A if i%2==0 else PIECE_B
   if (g.selected>>i)&1:f[y-2:y+3,x-2:x+3]=SELECTED
   if i==g.cursor:f[y-8:y-6,x-6:x+7]=CURSOR
  for i in range(6):x1,y1=pts[i];x2,y2=pts[(i+1)%6];f[min(y1,y2):max(y1+1,y2+1),min(x1,x2):max(x1+1,x2+1)]=CYCLE
  f[54:58,8:8+g.rank*8]=RANK;f[7:10,8:8+g.target_id*8]=TARGET;f[54:58,49:49+g.excess*3]=EXCESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A142(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a142",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.selected,self.cursor,self.target_id,self.rank,self.excess,self.history,self.snapshot=(0b000101,0,0,2,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.selected,self.cursor,self.target_id,self.rank,self.excess,self.history,self.snapshot=advance((self.selected,self.cursor,self.target_id,self.rank,self.excess,self.history,self.snapshot),a)
  elif a==6:
   if (self.selected,self.cursor,self.target_id,self.rank,self.excess,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
