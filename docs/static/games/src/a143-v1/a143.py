"""a143 Return Parity -- predict which target lies in the reachable parity class."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SLIDER,TILE_A,TILE_B,EMPTY,CYCLE,CURSOR,TARGET_A,TARGET_B,REACHABLE=10,8,12,14,7,9,13,4,11,6
BAD=15
LEVELS=[
 {"name":"Rotate Triple","seq":(1,)},{"name":"Select Window","seq":(2,)},
 {"name":"Choose Target","seq":(3,1)},{"name":"Read Parity","seq":(1,2,3,4,2)},
 {"name":"Reject Unreachable","seq":(1,3,2,1,4,3,2)},{"name":"Return Parity","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def parity(p):return sum(int(p[i]>p[j]) for i in range(len(p)) for j in range(i+1,len(p)))%2
def advance(s,a):
 pieces,cursor,target_choice,current_parity,reachable,history,snapshot=s;p=list(pieces)
 if a==1:
  ids=(cursor%6,(cursor+1)%8,(cursor+2)%8);p[ids[0]],p[ids[1]],p[ids[2]]=p[ids[2]],p[ids[0]],p[ids[1]];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:target_choice=1-target_choice;history=(history+(3,))[-8:]
 elif a==4:current_parity=parity(p);reachable=int(current_parity==target_choice);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),cursor,target_choice,current_parity,reachable,history)
 return tuple(p),cursor,target_choice,current_parity,reachable,history,snapshot
for q in LEVELS:
 s=((0,1,2,3,4,5,6,7),0,0,0,1,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SLIDER
  for i,v in enumerate(g.pieces):
   x=8+(i%4)*13;y=14+(i//4)*20;f[y:y+15,x:x+11]=TILE_A if v%2==0 else TILE_B;f[y+4:y+10,x+3:x+8]=EMPTY
   if i in (g.cursor,(g.cursor+1)%8,(g.cursor+2)%8):f[y-3:y,x:x+11]=CYCLE
  f[54:58,8:28]=TARGET_A if g.target_choice==0 else TARGET_B;f[54:58,31:55]=REACHABLE if g.reachable else BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A143(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a143",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pieces,self.cursor,self.target_choice,self.current_parity,self.reachable,self.history,self.snapshot=((0,1,2,3,4,5,6,7),0,0,0,1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pieces,self.cursor,self.target_choice,self.current_parity,self.reachable,self.history,self.snapshot=advance((self.pieces,self.cursor,self.target_choice,self.current_parity,self.reachable,self.history,self.snapshot),a)
  elif a==6:
   if (self.pieces,self.cursor,self.target_choice,self.current_parity,self.reachable,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
