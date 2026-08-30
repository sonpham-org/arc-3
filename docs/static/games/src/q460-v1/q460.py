"""q460 Vault Lineage -- track identities while redistributing two conserved quantities."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,ECHO,TRAIL,STOREA,STOREB,GATE,BAD=14,4,9,15,10,12,6,8
LEVELS=[
 {"name":"Ancestor and Store","ops":[1],"target_id":1,"a":[1,1,0],"b":[0,1,1]},
 {"name":"Appearance Exchange","ops":[2,1],"target_id":2,"a":[1,0,2],"b":[1,1,0]},
 {"name":"Dual Conservation","ops":[1,2,1],"target_id":3,"a":[0,2,1],"b":[1,0,2]},
 {"name":"Shared Containers","ops":[2,1,2,1],"target_id":1,"a":[2,1,1],"b":[1,2,1]},
 {"name":"Causal Trail","ops":[1,1,2,1,2],"target_id":2,"a":[1,2,2],"b":[2,1,2]},
 {"name":"Vault Lineage","ops":[2,1,2,2,1,2],"target_id":3,"a":[2,3,1],"b":[1,2,3]}]
def transform(p,op):
 p=list(p)
 if op==1:p[0],p[1]=p[1],p[0]
 else:p=p[1:]+p[:1]
 return p
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=VAULT
  for i in range(3):x=9+i*17;f[16:30,x:x+11]=ECHO;f[33:37,x:x+g.a[i]*4]=STOREA;f[39:43,x:x+g.b[i]*4]=STOREB;f[46:50,x:x+11]=GATE if i==g.cursor else TRAIL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q460(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.ops=[];self.target_id=self.progress=self.cursor=0;self.perm=[1,2,3];self.a=self.b=self.target_a=self.target_b=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q460",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.ops=list(s["ops"]);self.target_id=s["target_id"];self.progress=self.cursor=0;self.perm=[1,2,3];self.target_a=list(s["a"]);self.target_b=list(s["b"]);self.a=[sum(self.target_a),0,0];self.b=[sum(self.target_b),0,0];self.failed=False
 def step(self):
  z=self.action.id.value;nxt=(self.cursor+1)%3
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress<len(self.ops):
   if z!=self.ops[self.progress]:self.failed=True;self.lose()
   else:self.perm=transform(self.perm,z);self.progress+=1
  elif z in (3,4) and self.progress==len(self.ops):
   store=self.a if z==3 else self.b
   if store[self.cursor]<=0:self.failed=True;self.lose()
   else:store[self.cursor]-=1;store[nxt]+=1
  elif z==5 and self.progress==len(self.ops):self.cursor=nxt
  elif z==6:
   if self.progress==len(self.ops) and self.perm[self.cursor]==self.target_id and self.a==self.target_a and self.b==self.target_b:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
